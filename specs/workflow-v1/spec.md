# Crevis 工作流系统规格说明书

## 1. 背景

当前 Crevis 为单任务 CLI 工具。本 spec 将其升级为支持**版本化输入/输出、自动远程化、异步任务监听**的工作流系统。

## 2. 配置模块

### 2.1 配置文件

本地输入不依赖固定目录，用户从前端传入文件；本地输出路径用户可配置：

```json
{
  "api_key": "ak-xxxxxxxx",
  "provider": "volcengine",
  "model_id": "doubao-seedance-2-0-fast-260128",
  "oss": {
    "base_input_url": "https://your-bucket.com/inputs",
    "base_output_url": "https://your-bucket.com/outputs"
  },
  "local_output_path": "~/.crevis/outputs"
}
```

### 2.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `api_key` | string | 是 | 模型 API Key |
| `provider` | string | 是 | 模型提供方 |
| `model_id` | string | 是 | 模型 ID |
| `oss.base_input_url` | string | 是 | 远程输入存储基础 URL（如 OSS 前缀） |
| `oss.base_output_url` | string | 是 | 远程输出存储基础 URL（如 OSS 前缀） |
| `local_output_path` | string | 否 | **本地输出路径**，默认 `~/.crevis/outputs` |

**注意**：
- 提示词（prompt）**不在配置中**，每次提交时传入
- 视频时长（duration）**不在配置中**，从 prompt 中提取
- 生成参数（generate_audio, ratio, watermark）**不在配置中**，每次提交时从前端传入
- **本地输入路径不需要**，用户从前端传入文件

### 2.3 加载优先级

1. 环境变量 `CREVIS_CONFIG_PATH` 指定的路径
2. 默认路径 `~/.config/crevis.json`
3. 若不存在，引导用户创建

### 2.4 与现有系统关系

- 替换 `~/.ark.yaml` 读取逻辑
- `conf/input.yaml` 保留作为项目级覆盖（可选）

## 3. 输入模块

输入不再依赖本地目录，用户从前端直接传入文件（本地文件或 URL）。

### 3.1 输入来源

- **用户上传**：通过前端网页上传本地图片/视频/音频
- **URL 引用**：直接传入远程 URL（如 OSS 链接）

### 3.2 素材类型

| 类型 | 格式 |
|------|------|
| `image` | jpg, jpeg, png, gif, bmp, webp |
| `video` | mp4, avi, mov, mkv, wmv, flv |
| `audio` | mp3, wav, aac, flac, ogg, m4a, wma |

### 3.3 输入列表

```json
{
  "id": "uuid",
  "type": "image|video|audio",
  "local_path": "/absolute/path/to/file",
  "remote_url": null
}
```

- 本地文件：传入后自动推断类型，远程化后填充 `remote_url`
- URL：直接使用，`remote_url` = `local_path`

## 4. 输出模块

### 4.1 目录结构

```
{local_output_path}/
└── versions/
    └── {version}/
        └── seedance_{task_id}.mp4
```

### 4.2 版本输出创建

- 与版本输入同步创建，提交前确保本地目录存在
- 命名：`{local_output_path}/versions/{version}/`

### 4.3 结果下载

- 监听完成后，将远程视频 URL 下载到 `{local_output_path}/versions/{version}/`
- 同时复制到项目本地 `outputs/` 目录（兼容现有）

## 5. 提交任务模块

### 5.1 提交流程

```
用户准备提交
  │
  ├─→ 1. 生成版本号
  │     └── v20240621143000
  │
  ├─→ 2. 创建版本目录
  │     ├── 输入：从前端接收用户上传的文件
  │     └── 输出：{local_output_path}/versions/{version}/
  │
  ├─→ 3. 收集输入列表
  │     └── 接收用户从前端传入的文件（本地文件或 URL）
  │
  ├─→ 4. 输入远程化
  │     ├── 上传本地文件到远程存储
  │     │   └── {oss.base_input_url}/versions/{version}/{type}/filename
  │     └── 替换为 remote_url
  │
  ├─→ 5. 构建 API 请求参数
  │     ├── model, content（URL 列表 + prompt）
  │     └── generate_audio, ratio, duration, watermark（从前端传入）
  │
  ├─→ 6. 提交 API 任务
  │     └── 返回 task_id
  │
  ├─→ 7. 收集并持久化任务信息
  │     ├── task_id, version, input_list, output_path
  │     ├── model_id, request_params（API Key 脱敏为 "api_key"）
  │     └── created_at
  │
  └─→ 8. 提交给响应监听模块
```

### 5.2 版本号生成

- 格式：`v{timestamp}`（年月日时分秒）
- 示例：`v20240621143000`
- 同一用户范围内唯一

### 5.3 输入远程化

- 上传本地文件到 `{oss.base_input_url}/versions/{version}/{type}/filename`
- 若未配置远程存储，使用本地 HTTP 服务生成 URL
- 上传失败时中止提交，提示用户

### 5.4 请求参数脱敏

存储任务信息时，API Key 替换为 `"api_key"`：

```python
request_params = {
    "model": model_id,
    "content": [...],   # 远程化后的 URL 列表 + prompt
    "generate_audio": True,   # 前端传入
    "ratio": "16:9",          # 前端传入
    "duration": 5,            # 从 prompt 提取
    "watermark": False,       # 前端传入（默认不加）
    "api_key": "api_key"      # 脱敏
}
```

### 5.5 防重复提交

- 后端维护 `is_submitted` 标志，同一版本号只允许一次提交
- 提交失败（如网络错误）后，允许重置状态重新提交

## 6. 响应监听模块

### 6.1 监听任务创建

- 提交成功后，将 `task_id` 加入监听队列
- 数据结构：

```json
{
  "task_id": "task_xxx",
  "version": "v20240621143000",
  "output_local_path": "...",
  "status": "pending",
  "created_at": "2024-06-21T14:30:00",
  "result_url": null,
  "error_message": null
}
```

### 6.2 轮询策略

- 间隔：30 秒
- 超时：30 分钟（可配置）
- 每个任务独立监听

### 6.3 状态处理

| API 状态 | 行为 |
|----------|------|
| `pending` | 继续等待 |
| `running` | 继续等待 |
| `succeeded` | 下载视频到版本输出目录，复制到 `outputs/`，标记 `completed` |
| `failed` | 记录错误，标记 `failed` |
| 超时 | 标记 `timeout` |

### 6.4 下载逻辑

```python
def download_result(video_url: str, output_path: Path):
    download(video_url, output_path / "seedance_{task_id}.mp4")
    copy_to_local_outputs(output_path / "seedance_{task_id}.mp4")
```

### 6.5 任务信息持久化

存储在 `{local_output_path}/task_history.jsonl`：

```json
{
  "task_id": "task_abc123",
  "version": "v20240621143000",
  "status": "completed",
  "model_id": "doubao-seedance-2-0-fast-260128",
  "input_list": [
    {"type": "image", "url": "https://.../image1.jpg"}
  ],
  "output_local_path": "/Users/xxx/crevis-outputs/versions/v20240621143000",
  "output_url": "https://.../result.mp4",
  "request_params": {...},
  "created_at": "2024-06-21T14:30:00",
  "completed_at": "2024-06-21T14:35:00",
  "error_message": null
}
```

## 7. 数据模型

### 7.1 核心实体

```
Task
  ├── task_id: string
  ├── version: string
  ├── model_id: string
  ├── input_list: InputItem[]
  ├── output_path: Path
  ├── request_params: dict
  ├── status: pending|running|succeeded|failed|completed|timeout
  ├── created_at: datetime
  ├── completed_at: datetime
  └── error_message: string

InputItem
  ├── id: uuid
  ├── type: image|video|audio
  ├── source: default|version
  ├── local_path: Path
  └── remote_url: URL
```

### 7.2 状态机

```
[created] ──提交API──→ [pending] ──处理──→ [running] ──成功──→ [succeeded] ──下载──→ [completed]
                                                              │
                                                              └──失败──→ [failed]
                                                              │
                                                              └──超时──→ [timeout]
```

## 8. 模块职责

| 模块 | 职责 | 输出文件 |
|------|------|----------|
| ConfigManager | 读取 `~/.config/crevis.json` | `python/config_manager.py` |
| InputManager | 管理输入目录结构和引用 | `python/input_manager.py` |
| OutputManager | 管理输出目录和下载 | `python/output_manager.py` |
| TaskSubmitter | 版本创建、远程化、提交、持久化 | `python/task_submitter.py` |
| TaskListener | 异步监听和下载 | `python/task_listener.py` |
| Storage | 任务信息持久化 | `python/storage.py` |
| Models | 数据模型（Task, InputItem） | `python/models.py` |

## 9. 文件系统约定

```
~/.config/
└── crevis.json

~/.crevis/
└── outputs/                   # 本地输出（用户可配置 local_output_path）
    ├── versions/
    │   └── {version}/
    │       └── seedance_{task_id}.mp4
    ├── logs/
    │   └── crevis-2024-06-21.log
    └── task_history.jsonl     # 任务历史记录

{project_root}/
└── outputs/                   # 兼容现有
    └── seedance_{task_id}.mp4
```

## 10. 错误处理

| 场景 | 行为 |
|------|------|
| 配置不存在 | 引导创建模板 |
| 字段缺失 | 返回具体错误 |
| 素材不存在 | 提交时校验 |
| 格式不支持 | 导入时拒绝 |
| 上传失败 | 中止提交，提示用户 |
| API Key 无效 | 返回认证失败 |
| 任务超时 | 标记 `timeout`，打印日志 |
| 下载失败 | 记录 URL，用户可手动下载 |
| 磁盘空间不足 | 下载前检查 |

---

*本文档为 Crevis 工作流系统规格说明书，指导后续工程开发。*
