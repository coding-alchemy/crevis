# 提示词与模型网关模块

> 上级文档：[Crevis 项目架构规格说明](../architecture.md)

## 1. 模块目标

本模块负责提示词版本、上下文拼装、LLM 优化和各类生成模型适配。业务层使用统一请求模型，不直接依赖 Ark、Runway 或 OpenCode 的字段和状态。

## 2. 提示词模型

### 2.1 Prompt / PromptRevision

`Prompt` 表示逻辑提示词；`PromptRevision` 是不可变快照，保存：

- `purpose`: `storyboard/shot/keyframe/video/quality_check`；
- 用户原文；
- 模板 ID 和版本；
- 系统指令；
- 项目、人物、场景、前镜摘要等上下文引用；
- 渲染后的完整提示词；
- LLM 优化结果；
- 用户最终编辑；
- 输入上下文哈希、语言和修订关系。

原始提示词、优化结果和人工编辑必须分别保存，不覆盖历史。

### 2.2 LLMCall

每次 LLM 调用保存：

| 字段 | 说明 |
|---|---|
| `provider`, `model` | 实际调用目标 |
| `request_params` | 已脱敏参数 |
| `input_hash` | 模板、上下文和参数指纹 |
| `raw_response_object_key` | 大型原始响应附件 |
| `parsed_output` | Schema 校验后的结果 |
| `input_tokens`, `output_tokens`, `cost` | 用量与成本 |
| `latency_ms`, `status`, `error` | 运行信息 |
| `trace_id`, `node_run_id` | 链路关联 |

认证头、API Key 和密钥不进入数据库或附件。

## 3. 结构化输出

提示词优化应使用 JSON Schema，例如：

```json
{
  "optimized_prompt": "...",
  "negative_prompt": "...",
  "continuity": {
    "characters": ["character_asset_id"],
    "scene": "scene_asset_id",
    "camera": "medium tracking shot",
    "must_preserve": ["blue coat", "warm backlight"]
  },
  "generation": {
    "duration_seconds": 5,
    "ratio": "16:9"
  },
  "warnings": []
}
```

处理顺序：

```text
调用模型 → 解析 JSON → Schema 校验
        → 可控修复一次 → 失败则记录原始输出并终止节点
```

不再把自然语言正则作为时长等关键参数的唯一来源。旧请求可兼容解析，但必须落到结构化字段并让用户确认。

## 4. 上下文拼装

分镜提示词上下文按稳定顺序组成：

1. 模型供应商的系统约束；
2. 项目 `style_bible`；
3. 人物、声音、场景和道具 profile；
4. 当前 ShotRevision；
5. 上一镜批准结果摘要和实际尾帧引用；
6. 当前首帧、目标尾帧及连续性约束；
7. 用户本次修改；
8. 输出 JSON Schema。

保存上下文中使用的实体版本和 `input_hash`，保证结果可复盘。素材二进制通过受控 URL 或供应商支持的上传引用传递，不嵌入数据库字段。

## 5. LLM 适配器

```python
class LLMProvider(Protocol):
    def capabilities(self) -> LLMCapabilities: ...
    def complete_structured(
        self,
        request: StructuredPromptRequest,
        idempotency_key: str,
    ) -> StructuredPromptResult: ...
```

### 5.1 直接 API 适配器

生产环境优先直接 API，便于控制：

- 结构化输出和模型版本；
- 请求超时、限流和取消；
- token、费用与原始响应；
- 供应商数据策略和区域；
- 稳定错误分类。

### 5.2 OpenCode CLI 适配器

OpenCode 官方 CLI 支持使用 `opencode run` 程序化执行一次性提示词：[官方文档](https://dev.opencode.ai/docs/cli/)。Crevis 提供 `OpenCodeCliLLMAdapter` 作为本地和受控单机方案。

约束：

- 使用参数数组启动子进程，不做 shell 字符串拼接；
- 固定工作目录、模型白名单和权限；
- 设置超时、最大输出、最大并发和进程资源限制；
- stdout/stderr 分流，结构化结果经 Schema 校验；
- CLI 会话/日志作为附件保存，但不能替代 `LLMCall`；
- 生产多实例部署时，不依赖某台机器的本地会话状态。

## 6. 生成模型网关

内部定义 `VideoProvider`、`ImageProvider` 和 `AudioProvider`。视频接口示例：

```python
class VideoProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...
    def submit(self, request: VideoGenerationRequest, idempotency_key: str) -> ProviderReceipt: ...
    def get(self, provider_task_id: str) -> ProviderTaskSnapshot: ...
    def cancel(self, provider_task_id: str) -> None: ...
    def parse_webhook(self, headers: dict, body: bytes) -> ProviderEvent: ...
```

适配器职责：

- 能力校验和参数映射；
- 鉴权、限流、超时和错误归一化；
- 提交供应商任务，不持有业务工作流状态；
- webhook 验签或轮询；
- 原始响应留档和用量记录；
- 将供应商状态转换为内部状态。

供应商 task id 只在 `(provider, provider_task_id)` 范围唯一，不能作为 Crevis 主任务 ID。

## 7. 能力矩阵与路由

每个模型记录：

- 文生视频、图生视频、视频编辑；
- 首帧、尾帧、参考图、参考视频、参考音频；
- 时长、比例、分辨率和并发限制；
- webhook、取消、幂等支持；
- 内容安全、数据保留和区域；
- 预估成本和供应商配额。

工作流发布和运行前都要校验能力。首版按显式 provider/model 路由；后续可按能力、成本、质量和配额自动选择，但必须在任务记录中保存实际路由结果。

## 8. 缓存

LLM 可对相同 `template_version + context_hash + model + params` 做显式缓存。生成视频默认不透明缓存，因为用户通常期望新候选；只有工作流重放且幂等键相同时才复用已有任务。

## 9. API

```text
POST   /api/v1/prompts
GET    /api/v1/prompts/{id}/revisions
POST   /api/v1/prompts/{id}:optimize
POST   /api/v1/prompt-revisions/{id}:fork
GET    /api/v1/model-capabilities
GET    /api/v1/model-providers
```

## 10. 验收标准

- 每个最终提示词能追溯用户原文、模板、上下文、LLM 输出和人工编辑；
- 关键生成参数来自结构化字段并通过 Schema 校验；
- 领域与应用层不 import 供应商 SDK；
- Ark/Seedance 由 `VideoProvider` 适配器接入；
- OpenCode CLI 调用具备进程隔离、超时和结构化校验；
- 任务中记录实际供应商、模型、用量和费用，但不记录密钥；
- 工作流运行前能发现模型能力不匹配。
