# 工作流编排模块

> 上级文档：[Crevis 项目架构规格说明](../architecture.md)

## 1. 模块目标

工作流模块使用版本化 DAG 连接素材、提示词、关键帧、视频生成、质量检查、人工审批和合成节点，并将每次运行持久化。定义与执行分离：编辑工作流产生新版本，正在运行的实例继续使用原版本。

业界参考：ComfyUI 将生成工作流建模为节点图，并允许以 JSON 独立保存和版本化工作流。[官方文档](https://docs.comfy.org/development/core-concepts/workflow) Crevis 借鉴图和版本化思想，但首版只开放受控节点类型，不支持任意代码节点。

## 2. 领域模型

### 2.1 WorkflowDefinition / WorkflowVersion

`WorkflowDefinition` 保存逻辑名称、用途和所属工作区；`WorkflowVersion` 保存不可变内容：

- `schema_version`；
- 输入/输出 JSON Schema；
- 节点及其语义版本；
- 边和端口映射；
- 默认配置、失败策略和发布状态；
- 定义内容哈希、创建者和时间。

发布前校验 DAG 无环、端口类型匹配、配置合法、模型能力满足和必需输入可达。

### 2.2 WorkflowRun

一次运行绑定：

- `workflow_version_id`；
- `project_id`；
- `storyboard_revision_id`；
- 运行输入快照；
- 发起者、预算和优先级。

状态：

```text
draft → queued → running ⇄ waiting_input
                         ⇄ paused
       → succeeded | failed | cancelled
```

### 2.3 NodeRun

`NodeRun` 是一个展开后节点的一次逻辑执行：

```text
blocked → ready → queued → running
                         ├→ waiting_external → running
                         ├→ waiting_input → running
                         ├→ retry_scheduled → queued
                         └→ succeeded | failed | cancelled | skipped
```

关键字段：

| 字段 | 说明 |
|---|---|
| `expanded_node_key` | 运行内稳定节点键 |
| `node_type`, `node_version` | 执行实现 |
| `input_refs`, `output_refs` | 小型结构数据和资源 ID |
| `attempt_count`, `available_at` | 重试与调度 |
| `lease_owner`, `lease_expires_at`, `heartbeat_at` | Worker 租约 |
| `error_code`, `error_detail` | 归一化错误 |
| `started_at`, `finished_at` | 时序 |

队列中只传 `node_run_id` 和追踪信息，媒体二进制不进入数据库行或队列消息。

## 3. 节点契约

每个节点类型必须声明：

- `type` 和语义版本；
- 输入/输出端口及 JSON Schema；
- 配置 Schema 和默认值；
- 是否有外部副作用；
- 超时、最大重试次数和退避策略；
- 可重试错误集合；
- 幂等键生成规则；
- 所需 Worker 能力和资源类别；
- 取消和补偿能力。

节点执行器不得自行修改其他节点状态。它只提交自己的结果/错误，由编排服务在事务中推进 DAG。

## 4. 首批节点类型

| 节点 | 作用 |
|---|---|
| `asset.import` | 上传或导入输入素材 |
| `llm.storyboard` | 将创意/脚本拆为结构化分镜 |
| `llm.prompt.optimize` | 优化提示词并保留谱系 |
| `image.keyframe.start` | 生成或选定首帧 |
| `image.keyframe.end` | 生成目标尾帧 |
| `video.generate` | 生成分镜短视频 |
| `video.extract_frame` | 从实际片段抽取首/尾帧 |
| `quality.inspect` | 技术及可选语义检查 |
| `human.approval` | 等待批准、选择候选或要求重生成 |
| `video.normalize` | 统一片段编码规格 |
| `timeline.compose` | 构建 TimelineVersion |
| `video.render` | 合成长视频并回流素材库 |
| `notify` | 发送站内事件或外部通知 |

## 5. 复合节点

`shot.sequence` 表示“对分镜集合执行连续生成”的复合节点。存储时保留复合节点，创建运行时展开为可观察子节点：

```text
prompt.optimize
  → keyframe.start
  → keyframe.end
  → video.generate
  → quality.inspect
  → human.approval
  → video.extract_last_frame
```

串行模式下，第 N 镜 `extract_last_frame` 成功并批准后，才解锁第 N+1 镜 `keyframe.start`。预锁边界帧的并行模式可使用不同展开策略。

## 6. 示例定义

```json
{
  "schema_version": "1.0",
  "name": "storyboard-to-long-video",
  "inputs": {
    "project_id": {"type": "string"},
    "storyboard_revision_id": {"type": "string"}
  },
  "nodes": [
    {"id": "plan", "type": "llm.storyboard@1", "config": {}},
    {"id": "shots", "type": "shot.sequence@1", "config": {"mode": "sequential"}},
    {"id": "compose", "type": "timeline.compose@1", "config": {}},
    {"id": "render", "type": "video.render@1", "config": {"preset": "project"}}
  ],
  "edges": [
    {"from": "plan.storyboard", "to": "shots.storyboard"},
    {"from": "shots.approved_clips", "to": "compose.clips"},
    {"from": "compose.timeline", "to": "render.timeline"}
  ]
}
```

## 7. 调度流程

```text
创建 WorkflowRun
  → 展开节点并写入 blocked/ready 状态
  → 同事务写 Outbox
  → 发布器发送 ready 节点
  → Worker 用租约领取 NodeRun
  → 执行并提交结果
  → 编排服务推进下游
  → 全部必需终点成功后 Run succeeded
```

队列是唤醒机制，PostgreSQL 是状态真相源。定时 reconciliation 扫描：

- `ready` 但没有可见队列消息的节点；
- 过期租约；
- 长时间 `waiting_external` 的供应商任务；
- 依赖终态但未被推进的下游；
- 已取消运行中仍在执行的节点。

## 8. 人工交互

`human.approval` 进入 `waiting_input`，保存：

- 可选候选和预览素材；
- 提示问题与允许操作；
- 审批超时和默认策略；
- 当前提示词、关键帧及检查结果快照。

用户操作通过 API 产生命令事件，由编排服务验证运行版本与节点状态后恢复。前端不能直接更新节点状态字段。

## 9. 运行控制

- `pause`：不调度新节点，已在执行的外部任务继续同步；
- `resume`：重新计算 ready 节点并发布；
- `cancel`：标记运行取消，尽力取消供应商任务，保留已产生素材；
- `retry node`：复用逻辑输入并创建新 attempt；
- `fork from node`：创建新 WorkflowRun，引用上游不可变输出，从指定节点开始；
- `skip`：仅对定义声明为可跳过的节点开放。

## 10. 实现边界

首版使用 PostgreSQL + 任务队列自建轻量持久化编排。AWS Step Functions 等实现展示了状态、输入输出、执行历史和重试与业务实现分离的价值：[官方文档](https://aws.amazon.com/documentation-overview/step-functions/)。Temporal 则将外部 API 等副作用作为可恢复 Activity：[官方说明](https://temporal.io/)。

满足以下条件时再评估迁移专用编排平台：

- 跨服务工作流显著增加；
- 单次运行持续数日且升级兼容复杂；
- 补偿与信号交互大量增加；
- 当前调度吞吐或运维成本成为明确瓶颈；
- 需要多集群灾备。

领域中的 WorkflowDefinition、Run、NodeRun 和节点 Port 接口必须保持引擎无关，为迁移留出边界。

## 11. API

```text
POST   /api/v1/workflow-definitions
POST   /api/v1/workflow-definitions/{id}/versions
POST   /api/v1/workflow-versions/{id}:validate
POST   /api/v1/workflow-versions/{id}:publish
POST   /api/v1/workflow-runs
GET    /api/v1/workflow-runs/{id}
POST   /api/v1/workflow-runs/{id}:pause
POST   /api/v1/workflow-runs/{id}:resume
POST   /api/v1/workflow-runs/{id}:cancel
POST   /api/v1/node-runs/{id}:retry
POST   /api/v1/node-runs/{id}:approve
POST   /api/v1/node-runs/{id}:reject
POST   /api/v1/node-runs/{id}:fork
```

## 12. 验收标准

- 工作流定义可校验、发布和版本化；
- 旧运行不受定义编辑影响；
- 服务、发布器或 Worker 重启后运行可恢复；
- 同一节点的重复消息不会产生重复副作用；
- 人工审批可跨会话等待并恢复；
- 至少 5 个分镜可按尾帧依赖连续执行；
- 可暂停、取消、重试节点和从节点派生新运行；
- reconciliation 能修复丢消息和过期租约。
