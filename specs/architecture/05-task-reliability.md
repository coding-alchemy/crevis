# 任务与可靠性模块

> 上级文档：[Crevis 项目架构规格说明](../architecture.md)

## 1. 模块目标

本模块统一记录 LLM、图像、视频、媒体处理和渲染任务，并定义幂等、重试、租约、Outbox、供应商状态同步和审计语义。目标是“不丢任务、不重复计费、结果可追溯”。

## 2. 任务分层

### 2.1 NodeRun

工作流中的逻辑步骤，由编排模块拥有。它描述业务位置，不等于供应商请求。

### 2.2 GenerationTask

Crevis 的一次逻辑生成意图，例如“为 Shot 3 生成候选 2”。保存：

- 任务类型和领域对象；
- 归一化输入引用；
- 提示词修订和模型路由要求；
- 状态、预算、创建者；
- 最终输出素材版本。

### 2.3 GenerationAttempt

向某供应商的一次实际提交。一个逻辑任务可以因临时错误、供应商切换或人工新候选产生多个 attempt，但“基础设施重试”和“用户新候选”必须区分。

关键字段：

| 字段 | 说明 |
|---|---|
| `provider`, `model` | 实际路由 |
| `provider_task_id` | 供应商任务号 |
| `idempotency_key` | 本次逻辑副作用键 |
| `request_snapshot` | 已脱敏请求 |
| `raw_response_object_key` | 原始响应附件 |
| `status`, `error_code` | 归一化状态 |
| `submitted_at`, `provider_finished_at` | 供应商时序 |
| `usage`, `estimated_cost`, `actual_cost` | 成本 |

### 2.4 RenderTask / MediaTask

渲染与本地媒体处理也使用任务/attempt 思路，保存工具版本、输入输出校验和、命令摘要、日志和退出码。

## 3. 状态语义

供应商状态和系统状态分离：

```text
created → submitting → submitted → provider_running
       → provider_succeeded → result_pending → succeeded
       → failed | cancelled | timeout
```

`provider_succeeded` 只表示远端完成；只有结果已下载、校验、上传对象存储并创建 `AssetVersion` 后才是 `succeeded`。

## 4. 幂等

创建型 API 接收 `Idempotency-Key`。节点副作用键建议：

```text
sha256(workflow_run_id + node_run_id + logical_operation + input_fingerprint)
```

同一逻辑 attempt 重试时键保持稳定；用户主动“生成新候选”创建新 GenerationTask 和新键。

数据库唯一约束至少包括：

- `(workspace_id, idempotency_key)`；
- `(provider, provider_task_id)`；
- `(workflow_run_id, expanded_node_key)`；
- `(asset_id, version_no)`；
- 同一时间线版本和输出 preset 的活动 RenderTask。

若供应商不支持幂等键，提交前后都要保存本地 receipt，并在“请求超时、结果未知”时进入 reconciliation，不能立即盲目重提。

## 5. 事务 Outbox

业务状态和 outbox 事件在同一数据库事务写入：

```text
BEGIN
  更新任务/节点状态
  插入 outbox_event
COMMIT
```

发布器读取未发布事件、发送队列并记录 `published_at`。发布可能重复，因此消费者必须幂等。失败事件持续重试并告警。

禁止仅依赖“提交数据库后直接发消息”，否则进程在两步之间退出会永久丢任务。

## 6. Worker 租约

- Worker 以条件更新领取任务；
- 写入 `lease_owner`、`lease_expires_at` 和 `heartbeat_at`；
- 长本地任务定期 heartbeat；
- 调度器回收过期租约；
- 外部异步任务提交后进入 `waiting_external`，不长期占用 Worker 线程；
- 完成提交使用版本号/状态条件，防止过期 Worker 覆盖新结果。

## 7. 重试分类

| 类型 | 示例 | 策略 |
|---|---|---|
| 临时错误 | 429、5xx、网络超时 | 指数退避 + jitter，遵守 `Retry-After` |
| 异步等待 | pending/running | 延迟查询，不算失败重试 |
| 永久输入错误 | 参数无效、格式不支持 | 立即失败，等待用户修正 |
| 认证/配额 | key 无效、余额不足 | 暂停供应商队列并告警 |
| 结果搬运错误 | 下载或存储超时 | 只重试结果搬运 |
| 质量不达标 | 人物漂移、人工拒绝 | 创建新候选，不算基础设施重试 |

每类错误定义最大次数、最大延迟和最终处理。不得对所有异常使用同一无限重试策略。

## 8. webhook 与轮询

供应商支持 webhook 时优先使用：

- 验证签名、时间戳和事件 ID；
- 防重放并保存原始事件；
- 终态重复事件幂等处理；
- 返回成功前先持久化事件。

轮询作为不支持 webhook 和丢回调的兜底。轮询间隔使用退避和随机抖动，不为所有任务固定 30 秒。轮询任务本身由延迟队列或调度表驱动。

## 9. Reconciliation

定时任务检查：

- `submitting` 超时但可能已被供应商受理；
- `submitted/provider_running` 长时间无事件；
- `provider_succeeded` 但未完成结果搬运；
- `ready/retry_scheduled` 未入队；
- 租约过期；
- 已取消任务仍收到结果；
- 数据库状态与对象存储对象不一致。

修复动作本身也写审计事件。

## 10. 任务查询与审计

统一任务列表展示：

- Project/Shot/Node 上下文；
- 状态、进度、等待原因和重试次数；
- 原始/最终提示词、模型参数；
- 输入输出素材；
- 供应商任务和每个 attempt；
- 耗时、费用、错误和操作者；
- 状态事件时间线。

当前态存 PostgreSQL，状态变更写追加式事件表。JSONL 只保留为导入/导出或诊断格式，不再作为在线真相源。

## 11. 当前实现迁移

| 当前实现 | 迁移 |
|---|---|
| `TaskSubmitter` | `GenerationService + ProviderAdapter` |
| `_submitted_versions` 内存集合 | 数据库幂等键和唯一约束 |
| 秒级版本号 | UUIDv7/ULID；展示版本单独生成 |
| `TaskListener` 守护线程 | 持久化 Worker + 延迟调度 |
| 固定 30 秒轮询 | webhook 优先、退避轮询兜底 |
| JSONL 整文件更新 | 任务当前态表 + 事件表 |
| 下载失败后仅打印 URL | `result_pending` 并重试搬运 |

## 12. API

```text
GET    /api/v1/tasks
GET    /api/v1/tasks/{id}
GET    /api/v1/tasks/{id}/attempts
GET    /api/v1/tasks/{id}/events
POST   /api/v1/tasks/{id}:cancel
POST   /api/v1/tasks/{id}:retry
GET    /api/v1/events/stream
```

## 13. 验收标准

- API、Worker 或队列重启不丢任务；
- 重复消息和 webhook 不产生重复副作用；
- 相同幂等请求不重复提交或计费；
- 提交超时且结果未知时不会盲目重提；
- 供应商成功但下载失败时只重试搬运；
- 每个任务和 attempt 可查询输入、输出、状态、费用和错误；
- reconciliation 能发现并修复中间状态；
- 任务记录、日志和响应中没有明文密钥。
