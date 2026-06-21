# Crevis — 项目架构与开发者指南

> **注意**：这是给 AI 编码助手的参考文档（AGENTS.md），如果你是人类开发者，请从 README.md 开始。

## 项目概述

Crevis 是一个基于 **Seedance 2.0**（字节火山引擎）视频生成模型的 Python 项目。核心功能：通过文本提示词、参考图片和参考视频，调用 Seedance 2.0 模型进行视频编辑或生成。

项目代号：Crevis（Creative Video）。

## 技术栈

- **Python 3.12**
- **SDK**: `volcengine-python-sdk[ark]`（volcenginesdkarkruntime）
- **配置管理**: YAML（PyYAML）
- **环境管理**: `uv`（推荐）或 `venv`

## 项目结构

```
crevis/
├── conf/                       # 配置层
│   ├── .ark.yaml.example      # 上层 API Key 配置模板
│   └── input.yaml              # 主配置文件（视频生成参数、模型、内容、路径）
├── python/                      # 核心代码层
│   ├── config_loader.py       # 配置加载器（多级配置、验证、路径解析）
│   └── video_generator.py     # 主程序：配置驱动的视频生成任务
├── scripts/                     # 自动化脚本
│   └── init_dev_env/
│       ├── setup_mac.sh       # macOS 环境初始化（使用 uv）
│       └── setup_windows.bat  # Windows 环境初始化
├── run.sh                       # 项目启动脚本（调用 video_generator.py）
├── .gitignore
└── README.md
```

## 架构分层

### 1. 配置层（conf/）

项目采用**多级配置**策略，支持敏感信息与业务参数分离：

**配置文件层级**（优先级从高到低）：
1. 环境变量 `ARK_API_KEY`（最高优先级）
2. 上层配置文件：`~/.ark.yaml` 或 `../.ark.yaml`（存放 API Key 等敏感信息）
3. 项目内配置文件：`conf/input.yaml`（业务参数、模型配置、路径）
4. 默认配置（代码内 `DEFAULT_CONFIG`）

**关键配置项**（`conf/input.yaml`）：
- `api`: API Key（可留空，从上层配置或环境变量获取）
- `model`: 模型 ID（默认 `doubao-seedance-2-0-fast-260128`）
- `content`: 提示词、参考图片、参考视频、参考音频
- `paths`: 输入/输出目录（相对于上层目录）
- `generation`: 音频生成、视频比例、时长、水印

**路径解析规则**：
- `reference_image_url` / `reference_video_url` / `reference_audio_url`：
  - 以 `http://` 或 `https://` 开头 → 视为 URL 直接使用
  - 否则 → 视为相对于**上层目录**的路径，自动解析为绝对路径
- 输出目录默认为上层目录的 `outputs/`

### 2. 配置加载器（config_loader.py）

`ConfigLoader` 是核心配置管理类，职责：
- 多级配置加载与合并（`DEFAULT_CONFIG` → `input.yaml` → `.ark.yaml` → `ARK_API_KEY`）
- 路径解析（URL 与本地文件路径自动转换）
- 配置验证（`validate()`）：检查 API Key、模型 ID、提示词、文件存在性等
- 配置摘要打印（`print_config()`）

**关键方法**：
- `get_api_key()`: 按优先级获取 API Key
- `get_reference_image_path()`: 获取解析后的参考图片路径
- `get_output_dir()`: 获取并创建输出目录
- `get_output_path(filename)`: 获取输出文件路径
- `list_images() / list_videos()`: 列出输入目录中的媒体文件

### 3. 业务逻辑层（video_generator.py）

主程序，配置驱动的视频生成流程：

```
main()
├── 1. 加载配置 ConfigLoader()
├── 2. 验证配置 validate()
├── 3. 打印配置摘要 print_config()
├── 4. 初始化 Ark 客户端
├── 5. 读取并解析参数（模型、提示词、素材路径、生成参数）
├── 6. 生成浏览器预览页面（bin/preview.html）
├── 7. 调用 API 创建生成任务
│   └── content_generation.tasks.create(...)
├── 8. 轮询任务状态
│   └── content_generation.tasks.get(task_id)
│   └── 成功 → 下载视频到输出目录
│   └── 失败 → 打印错误信息
```

**API 调用参数**：
- `model`: 模型 ID
- `content`: 包含 text、image_url、video_url（可选 audio_url）的列表
- `generate_audio`: 是否生成音频
- `ratio`: 视频比例（16:9, 9:16, 1:1, 4:3, 3:4）
- `duration`: 视频时长（当前支持 5 秒）
- `watermark`: 是否添加水印

## 环境初始化

```bash
# macOS / Linux
bash scripts/init_dev_env/setup_mac.sh

# Windows
scripts/init_dev_env/setup_windows.bat
```

脚本会：
1. 检查/安装 `uv` 工具
2. 创建虚拟环境 `.venv`（Python 3.12）
3. 安装 `volcengine-python-sdk[ark]` 和 `PyYAML`
4. 生成启动脚本 `run.sh`

## 运行项目

```bash
# 方式一：使用 run.sh（推荐）
./run.sh

# 方式二：手动激活虚拟环境后运行
source .venv/bin/activate
python python/video_generator.py
```

## 开发规范

### 代码风格
- 遵循 Python 3.12 语法
- 使用类型注解（`Optional`, `Dict`, `Any`, `List`）
- 函数和类必须有文档字符串（docstring）
- 配置使用 `config_loader.py` 统一管理，避免硬编码

### 配置管理
- **敏感信息**（API Key）必须放在上层配置文件（`~/.ark.yaml` 或 `../.ark.yaml`），不要提交到 Git
- **业务参数**放在 `conf/input.yaml`
- 不要在代码中硬编码 API Key

### 路径约定
- 输入文件（图片、视频）默认放在上层目录的 `images/` 和 `videos/` 中
- 输出文件默认放在上层目录的 `outputs/` 中
- 项目代码中只处理绝对路径或 URL

### 新增功能时
1. 在 `conf/input.yaml` 中添加新配置项（如有必要）
2. 在 `config_loader.py` 的 `DEFAULT_CONFIG` 和对应 getter 方法中注册
3. 在 `video_generator.py` 中调用新的配置获取方法
4. 确保新配置在 `validate()` 中进行验证

## 依赖列表

核心依赖：
- `volcengine-python-sdk[ark]`：火山引擎方舟 SDK
- `PyYAML`：YAML 配置解析

标准库依赖：
- `os`, `time`, `urllib.request`, `pathlib`, `copy`, `webbrowser`

## 注意事项

1. **API Key 安全**：不要在代码中硬编码 API Key，使用环境变量或上层配置文件
2. **权限**：需要开通 Seedance 2.0 模型权限，详见控制台
3. **轮询间隔**：任务状态轮询每 30 秒一次，生成时间可能较长（几分钟）
4. **浏览器预览**：运行时会自动生成 `preview.html` 并打开浏览器，展示输入素材和提示词
5. **下载失败**：生成成功后，如果下载失败，会打印视频 URL，可手动下载
