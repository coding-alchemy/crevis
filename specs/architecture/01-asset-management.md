# 素材管理模块

> 上级文档：[Crevis 项目架构规格说明](../architecture.md)

## 1. 模块目标

素材模块统一管理图片、视频、声音、字幕、字体和生成结果，提供上传、远程导入、版本、检索、派生关系及授权治理。人物库、声音库、场景库是素材库上的结构化视图，不建设三套独立文件系统。

模块必须满足：

- 原始文件不可变，编辑和处理结果创建新版本；
- 媒体二进制放对象存储，数据库只保存定位和元数据；
- 所有生成结果回流素材库，并能追溯到输入、节点和模型任务；
- 工作流只能引用 `ready` 状态的具体 `AssetVersion`；
- 第三方 URL 不是长期资产地址，必须导入受控存储。

## 2. 领域模型

### 2.1 Asset

`Asset` 表示用户理解的逻辑素材，例如“主角小蓝”“咖啡馆夜景”“旁白声音 A”。

| 字段 | 说明 |
|---|---|
| `id` | UUIDv7/ULID |
| `workspace_id` | 所属空间 |
| `kind` | `image/video/audio/document/font/subtitle` |
| `category` | `character/voice/scene/prop/music/reference/generated/other` |
| `name`, `description` | 展示信息 |
| `tags` | 检索标签 |
| `license_metadata` | 来源、授权范围、到期时间 |
| `status` | `active/archived` |
| `created_by`, `created_at` | 审计字段 |

### 2.2 AssetVersion

`AssetVersion` 表示不可变的具体文件。

| 字段 | 说明 |
|---|---|
| `id`, `asset_id`, `version_no` | 版本身份 |
| `storage_provider`, `object_key` | 对象存储定位 |
| `sha256`, `size_bytes`, `mime_type` | 完整性和去重 |
| `width`, `height`, `duration_ms`, `fps` | 媒体规格 |
| `video_codec`, `audio_codec`, `sample_rate`, `channels` | 编解码元数据 |
| `source_type` | `upload/url_import/provider_output/derived` |
| `status` | `uploading/processing/ready/quarantined/failed/deleted` |
| `metadata` | 色彩空间、供应商响应摘要等扩展数据 |
| `created_by`, `created_at` | 审计字段 |

数据库不长期保存签名 URL。读取时由存储适配器根据 `object_key` 生成短期 URL。

### 2.3 AssetRelation

`AssetRelation` 保存素材谱系：

| 关系 | 示例 |
|---|---|
| `extract_first_frame` | 视频派生首帧图片 |
| `extract_last_frame` | 视频派生尾帧图片 |
| `generate_image` | 参考图和提示词生成关键帧 |
| `generate_video` | 图片和提示词生成短视频 |
| `normalize` | 原视频转成统一规格视频 |
| `compose` | 多个片段和音轨合成长视频 |
| `thumbnail/proxy/waveform` | 预览派生物 |

关系保存 `source_version_id`、`derived_version_id`、`relation_type`、`node_run_id` 和参数摘要。人工操作没有节点运行时，应保存审计事件 ID。

## 3. 人物、声音和场景库

### 3.1 CharacterProfile

- `asset_id`；
- 外观描述、年龄范围和显著特征；
- 服装与可变/不可变元素；
- 正面、侧面、全身等参考图版本；
- 负面约束；
- 可选角色一致性模型或 LoRA 引用。

### 3.2 VoiceProfile

- `asset_id`；
- 说话人、语言、音色和风格；
- 参考音频版本；
- TTS/声音模型的供应商引用；
- 肖像/声音授权范围和到期时间。

### 3.3 SceneProfile

- `asset_id`；
- 地点、时段、天气、光线和色板；
- 空间关系和不可变陈设；
- 参考图片/视频版本；
- 镜头方向和连续性备注。

Profile 的结构化字段用于提示词拼装和连续性检查，媒体文件仍由 `AssetVersion` 管理。

## 4. 对象存储

首版使用 S3 兼容接口，本地环境可使用 MinIO。对象键建议：

```text
workspaces/{workspace_id}/assets/{asset_id}/versions/{version_id}/original.{ext}
workspaces/{workspace_id}/assets/{asset_id}/versions/{version_id}/derived/{purpose}.{ext}
workspaces/{workspace_id}/runs/{run_id}/attachments/{attachment_id}.{ext}
```

`ObjectStorageAdapter` 至少提供：

```python
class ObjectStorage(Protocol):
    def begin_upload(self, object_key: str, content_type: str, size: int) -> UploadReceipt: ...
    def stat(self, object_key: str) -> ObjectMetadata: ...
    def open_reader(self, object_key: str): ...
    def put_file(self, object_key: str, local_path: Path, content_type: str) -> None: ...
    def signed_get_url(self, object_key: str, expires_in: int) -> str: ...
    def delete(self, object_key: str) -> None: ...
```

当前 `RemoteUploader` 只构造 URL，并未上传文件，必须由此适配器替代。URL 映射不能视为上传成功。

## 5. 素材入库流程

### 5.1 客户端直传

```text
1. 创建 Asset 和 uploading 状态的 AssetVersion
2. API 返回短期上传签名 URL
3. 客户端直接上传对象存储
4. 客户端调用 complete-upload
5. 服务校验对象大小、校验和与声明类型
6. 媒体 Worker 解析元数据并生成预览派生物
7. 检查通过后状态变为 ready
```

完成上传接口必须幂等。重复确认不能创建多个版本。

### 5.2 URL 导入

```text
1. API 校验 URL 协议和域名
2. Worker 在受控环境下载到临时文件
3. 校验大小、MIME、魔数和媒体可读性
4. 计算 SHA-256 并上传对象存储
5. 创建 ready AssetVersion 和来源信息
```

下载必须防 SSRF：仅允许 HTTP(S)，阻止回环、链路本地、云元数据及私网地址，限制重定向、DNS 重绑定、文件大小、超时和 Content-Type。

### 5.3 供应商结果入库

供应商返回成功后：

1. 将结果状态置为 `result_pending`；
2. 下载到受控临时文件；
3. 校验文件和媒体规格；
4. 上传对象存储并创建 `AssetVersion`；
5. 写入 `AssetRelation`；
6. 最后把系统任务置为成功。

结果搬运失败只重试下载/上传，不重新提交昂贵的生成任务。

## 6. 元数据与派生处理

媒体 Worker 使用 ffprobe 或格式解析器提取真实元数据，不信任客户端声明。派生任务包括：

- 图片缩略图和 EXIF 清理；
- 视频海报、低码率代理、首尾帧和联系表；
- 音频波形、时长和响度；
- 工作流需要的统一格式版本。

派生处理也是可观察任务，保存输入版本、工具版本、参数、日志和输出版本。

## 7. 搜索与引用

首版支持按工作区、类型、分类、标签、名称、状态和创建时间筛选。人物/声音/场景作为预设筛选入口。

删除前必须查询反向引用：

- Project/Shot 是否引用；
- WorkflowRun/NodeRun 是否作为输入输出；
- TimelineVersion/RenderTask 是否引用；
- 是否是其他 AssetVersion 的派生源。

仍被不可变版本或审计记录引用时只能归档或软删除，不能物理删除。

## 8. API

```text
POST   /api/v1/assets
GET    /api/v1/assets
GET    /api/v1/assets/{id}
PATCH  /api/v1/assets/{id}
POST   /api/v1/assets/{id}:archive
POST   /api/v1/assets/{id}/versions:begin-upload
POST   /api/v1/assets/{id}/versions/{version_id}:complete-upload
POST   /api/v1/assets:import-url
GET    /api/v1/asset-versions/{id}
GET    /api/v1/asset-versions/{id}/download-url
GET    /api/v1/asset-versions/{id}/lineage
```

## 9. 验收标准

- 本地上传、URL 导入和供应商输出均形成不可变 `AssetVersion`；
- 对象存储中存在真实文件后，版本才可进入 `ready`；
- 任意派生素材能反查来源、处理参数和节点运行；
- 人物、声音、场景可复用同一素材底座并提供结构化 profile；
- 签名 URL 过期不影响数据库记录；
- SSRF、伪造 MIME、超限文件和越权引用被拒绝；
- 被项目或运行引用的素材不会被物理删除。
