# API 与前端模块

> 上级文档：[Crevis 项目架构规格说明](../architecture.md)

## 1. 模块目标

API 为 Web、CLI 和自动化调用提供统一应用入口；前端围绕项目、素材、分镜、运行和时间线组织创作流程。CLI 与 Web 必须调用相同应用服务，不再维护两套生成逻辑。

## 2. API 职责

- 身份认证和 Workspace 访问控制；
- 请求/响应 Schema 校验；
- 幂等键、分页和稳定错误码；
- 调用应用用例并控制事务边界；
- 生成对象存储签名 URL；
- REST 查询与 SSE/WebSocket 状态事件；
- 接收供应商 webhook；
- 不在 HTTP 请求线程等待生成或渲染完成。

API 层不得直接调用供应商 SDK、FFmpeg 或操作队列内部状态。

## 3. 通用约定

### 3.1 标识和路径

- 系统 ID 使用 UUIDv7/ULID；
- 响应不暴露服务器绝对路径；
- 媒体引用使用 `asset_version_id`；
- 供应商 task id 只出现在任务详情的供应商字段；
- URL 作为字符串/URL 类型处理，不转换为 `Path`。

### 3.2 幂等

创建和副作用接口接受 `Idempotency-Key`。相同工作区、键和请求指纹返回原响应；相同键但请求体不同返回冲突。

### 3.3 错误

```json
{
  "error": {
    "code": "ASSET_NOT_READY",
    "message": "素材仍在处理中",
    "details": {"asset_version_id": "av_01"},
    "trace_id": "tr_01"
  }
}
```

`code` 稳定供客户端判断；`message` 可本地化；内部栈、密钥和供应商认证信息不返回。

### 3.4 查询

- 大列表使用游标分页；
- 所有查询强制 workspace 条件；
- 支持 `status/type/category/project_id/created_at` 等稳定过滤；
- 详情按需展开，避免列表返回大型 prompt、日志和事件集合。

## 4. API 资源

### 4.1 素材

```text
POST   /api/v1/assets
GET    /api/v1/assets
GET    /api/v1/assets/{id}
POST   /api/v1/assets/{id}/versions:begin-upload
POST   /api/v1/assets/{id}/versions/{version_id}:complete-upload
POST   /api/v1/assets:import-url
GET    /api/v1/asset-versions/{id}/download-url
```

### 4.2 项目与分镜

```text
POST   /api/v1/projects
GET    /api/v1/projects/{id}
POST   /api/v1/projects/{id}/storyboards
POST   /api/v1/storyboards/{id}/revisions
POST   /api/v1/storyboard-revisions/{id}:publish
POST   /api/v1/shots/{id}/revisions
POST   /api/v1/shot-candidates/{id}:approve
POST   /api/v1/shot-candidates/{id}:reject
```

### 4.3 提示词与模型

```text
POST   /api/v1/prompts/{id}:optimize
GET    /api/v1/prompts/{id}/revisions
GET    /api/v1/model-capabilities
```

### 4.4 工作流与任务

```text
POST   /api/v1/workflow-definitions
POST   /api/v1/workflow-definitions/{id}/versions
POST   /api/v1/workflow-runs
GET    /api/v1/workflow-runs/{id}
POST   /api/v1/workflow-runs/{id}:pause
POST   /api/v1/workflow-runs/{id}:resume
POST   /api/v1/workflow-runs/{id}:cancel
POST   /api/v1/node-runs/{id}:retry
POST   /api/v1/node-runs/{id}:approve
GET    /api/v1/tasks
GET    /api/v1/tasks/{id}
GET    /api/v1/events/stream
```

### 4.5 时间线与渲染

```text
POST   /api/v1/timelines
POST   /api/v1/timelines/{id}/versions
POST   /api/v1/timeline-versions/{id}:render
GET    /api/v1/render-tasks/{id}
```

## 5. 实时状态

首版优先 SSE：浏览器按 Workspace/Project/Run 订阅状态事件。事件只含摘要和实体 ID，例如：

```json
{
  "event_id": "evt_01",
  "type": "node_run.status_changed",
  "workspace_id": "ws_01",
  "project_id": "prj_01",
  "workflow_run_id": "run_01",
  "node_run_id": "node_03",
  "status": "waiting_input",
  "occurred_at": "2026-07-05T12:00:00Z"
}
```

客户端断线后使用 `Last-Event-ID` 或事件游标补取。实时通道不是状态真相源，刷新后必须能通过 REST 重建页面。

## 6. 前端信息架构

### 6.1 项目工作台

- 项目规格和风格圣经；
- 最近工作流、费用、失败和待审核；
- 从脚本创建分镜；
- 成片和最近渲染版本。

### 6.2 素材库

- 网格/列表、标签和人物/声音/场景筛选；
- 上传、URL 导入、版本和来源；
- 图片预览、视频代理和音频波形；
- 素材谱系及被引用位置；
- 授权和到期提示。

### 6.3 分镜板

- Shot 卡片显示首帧、目标尾帧、实际尾帧、候选和状态；
- 拖拽排序、批量锁定和提示词编辑；
- 相邻 ContinuityLink 可视化；
- 上游变更后的下游 stale 范围；
- 批准、拒绝和新建候选。

### 6.4 工作流运行

- 节点图展示状态、依赖、重试和等待原因；
- 节点抽屉展示输入输出、提示词、供应商任务、日志和费用；
- 暂停、取消、重试、审批和 fork；
- 失败节点突出显示并给出可执行修复动作。

### 6.5 时间线与导出

- 分镜顺序、转场、字幕和音轨；
- 低清代理预览；
- Timeline 版本和变更；
- 渲染参数、进度、历史与成片下载。

## 7. CLI

CLI 是 API 客户端，提供：

```text
crevis asset upload ...
crevis project create ...
crevis workflow run ...
crevis run status ...
crevis task list ...
crevis render ...
```

开发/单机模式可在同进程调用 application service，但命令语义和 Schema 必须与 HTTP API 一致。

## 8. 前端权限与冲突

- `owner/editor/viewer` 基础角色；
- 编辑接口使用资源版本或 ETag 做乐观并发控制；
- 审批接口验证节点仍处于 `waiting_input`；
- 签名 URL 仅对有素材读取权限的用户生成；
- 前端不保存供应商密钥。

## 9. 验收标准

- Web 与 CLI 使用同一应用用例和状态语义；
- 创建接口支持持久化幂等；
- 页面刷新可从 REST 恢复，断线事件可补取；
- 前端覆盖素材、分镜、运行和时间线的核心流程；
- 用户能从任务/节点跳转到输入输出素材和提示词；
- API 不暴露绝对路径、密钥和内部异常栈；
- Workspace 越权和并发覆盖被阻止。
