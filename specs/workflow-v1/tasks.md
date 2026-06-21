# Crevis 工作流系统开发任务清单

> 根据 spec.md 制定，按依赖顺序排列。每个任务需完成后才能开始依赖它的任务。

---

## Phase 1: 基础模块（无依赖）

### Task 1: 定义数据模型

**文件**: `python/models.py`

**实现内容**:
- `InputItem` dataclass：id, type, source, local_path, remote_url
- `Task` dataclass：task_id, version, model_id, input_list, output_path, request_params, status, created_at, completed_at, error_message
- 状态常量：PENDING, RUNNING, SUCCEEDED, FAILED, COMPLETED, TIMEOUT
- 辅助方法：to_dict, from_dict

**验收标准**:
- [ ] 可以创建 InputItem 和 Task 实例
- [ ] 可以序列化为 dict 并反序列化
- [ ] 状态常量为字符串且值正确

---

### Task 2: 配置管理器

**文件**: `python/config_manager.py`

**实现内容**:
- `ConfigManager` 类
- 加载逻辑：先读 `CREVIS_CONFIG_PATH` 环境变量，再读 `~/.config/crevis.json`
- 属性：api_key, provider, model_id, oss_base_input_url, oss_base_output_url, local_output_path
- `validate()` 方法：检查必填字段（api_key, provider, model_id）
- 若配置不存在，生成模板文件并提示用户编辑
- 本地输出路径用户可配置：`local_output_path`（默认 `~/.crevis/outputs`）

**验收标准**:
- [ ] 配置存在时正确加载所有字段
- [ ] 配置不存在时生成模板并抛出可读错误
- [ ] 必填字段缺失时 validate() 返回错误列表
- [ ] OSS URL 可选但缺失时给出警告
- [ ] 本地输出路径默认为 `~/.crevis/outputs`，用户可配置
- [ ] 配置模板包含 `local_output_path` 字段

---

### Task 3: 持久化存储

**文件**: `python/storage.py`

**实现内容**:
- `Storage` 类
- 使用 JSONL 格式存储到 `~/.crevis/outputs/task_history.jsonl`
- 方法：save_task(task), get_task(task_id), list_tasks(), update_task_status(task_id, status, error_message)
- 每个 task 存储为 JSON 对象，追加到文件
- 读取时按行解析，支持过滤

**验收标准**:
- [ ] 可以保存 Task 并读取
- [ ] 可以按 task_id 查询单个任务
- [ ] 可以列出所有任务
- [ ] 可以更新任务状态
- [ ] 文件不存在时自动创建

---

## Phase 2: 输入/输出管理（依赖 Phase 1）

### Task 4: 输入管理器

**文件**: `python/input_manager.py`

**依赖**: Task 1（models）, Task 2（config_manager）

**实现内容**:
- `InputManager` 类，不再依赖本地输入目录
- 方法：
  - `create_items(files)` → 从用户传入的文件路径创建 InputItem 列表
  - 支持本地文件和 URL
  - `remove_input(item)` → 清理引用（不删本地文件）

**验收标准**:
- [ ] 可以从用户传入的文件路径创建 InputItem
- [ ] 支持 URL 类型（自动标记为已远程化）
- [ ] 支持本地文件（推断类型）
- [ ] 移除输入时不删本地文件

---

### Task 5: 输出管理器

**文件**: `python/output_manager.py`

**依赖**: Task 2（config_manager）

**实现内容**:
- `OutputManager` 类，接收 `local_output_path`（用户可配置）
- 方法：
  - `create_version_output(version)` → 创建 `versions/{version}/` 目录
  - `download_result(video_url, version, filename)` → 下载到 `versions/{version}/filename`，同时复制到 `outputs/` 目录

**验收标准**:
- [ ] 可以创建版本输出目录
- [ ] 下载远程视频到正确路径
- [ ] 同时复制到项目 `outputs/` 目录
- [ ] 下载失败时抛出异常

---

## Phase 3: 核心工作流（依赖 Phase 2）

### Task 6: 输入远程化

**文件**: `python/remote_uploader.py`（或集成到 input_manager.py）

**依赖**: Task 4（input_manager）, Task 2（config_manager）

**实现内容**:
- 上传本地文件到远程存储
- 若配置了 `oss.base_input_url`，按 `{base_url}/versions/{version}/{type}/filename` 上传
- 若未配置，使用本地 HTTP 服务生成 `file://` URL（或本地可访问 URL）
- 上传成功后返回 remote_url，更新 InputItem
- 上传失败时中止，返回错误

**验收标准**:
- [ ] 配置 OSS 时正确上传并返回 URL
- [ ] 未配置 OSS 时生成本地 URL
- [ ] 上传失败时返回错误，不修改 InputItem

---

### Task 7: 提交任务模块

**文件**: `python/task_submitter.py`

**依赖**: Task 1-6（所有基础模块）

**实现内容**:
- `TaskSubmitter` 类，接收 config, input_mgr, output_mgr, storage
- 方法：
  - `generate_version()` → 返回 `v{timestamp}`
  - `submit(prompt, input_files, generation_params, include_default)` → 完整提交流程：
    1. 生成版本号
    2. 创建版本输出目录（输入不依赖本地目录）
    3. 从用户传入的文件构建输入列表
    4. 远程化所有输入
    5. 从 prompt 中提取 duration
    6. 构建 API 请求参数（model, content, generation_params + duration）
    7. 调用 API 提交任务，获取 task_id
    8. 收集任务信息（task_id, version, input_list, output_path, model_id, request_params 脱敏）
    9. 持久化到 Storage
    10. 返回 Task 对象
  - 防重复提交：检查 `is_submitted` 标志

**验收标准**:
- [ ] 生成版本号格式正确且唯一
- [ ] 创建目录结构正确
- [ ] 包含默认输入时正确合并
- [ ] 提交成功返回 Task 对象，包含正确 task_id
- [ ] 持久化文件中 API Key 已脱敏
- [ ] 重复提交同版本时拒绝

---

### Task 8: 响应监听模块

**文件**: `python/task_listener.py`

**依赖**: Task 5（output_manager）, Task 3（storage）, Task 1（models）

**实现内容**:
- `TaskListener` 类，接收 config, output_mgr, storage
- 方法：
  - `start_listening(task)` → 启动后台线程轮询
  - `poll_status(task_id)` → 调用 API 查询状态
  - 轮询逻辑：每 30 秒查询一次，最大 30 分钟
  - 状态处理：
    - pending/running：继续等待
    - succeeded：下载结果，更新状态为 completed
    - failed：记录错误，更新状态为 failed
    - 超时：标记 timeout
- 每个任务独立监听

**验收标准**:
- [ ] 可以启动监听并在后台运行
- [ ] 正确轮询状态（30 秒间隔）
- [ ] 任务成功时下载到正确路径并更新状态
- [ ] 任务失败时记录错误并更新状态
- [ ] 超时时标记 timeout
- [ ] 多个任务可以并行监听

---

## Phase 4: CLI 集成（依赖 Phase 3）

### Task 9: CLI 入口

**文件**: `python/main.py` 或更新 `python/video_generator.py`

**依赖**: Task 7（task_submitter）, Task 8（task_listener）

**实现内容**:
- 加载配置（ConfigManager）
- 初始化所有管理器（InputManager, OutputManager, Storage）
- 提供命令：
  - `submit`：接收 prompt + 生成参数（generate_audio, ratio, watermark），导入素材、提交任务、启动监听
  - `list`：列出所有任务
  - `status`：查询任务状态
- 支持 `--include-default` 开关
- 提交后显示任务信息，启动监听

**验收标准**:
- [ ] 可以完整执行一次提交→监听→下载流程
- [ ] 可以列出历史任务
- [ ] 可以查询指定任务状态
- [ ] 包含默认输入时正确合并
- [ ] 提交后防重复提交

---

### Task 10: 更新运行脚本

**文件**: `run.sh`

**依赖**: Task 9（CLI 入口）

**实现内容**:
- 更新 `run.sh` 调用新的 CLI 入口
- 支持传递参数（如 `--include-default`）

**验收标准**:
- [ ] `./run.sh` 可以启动新工作流
- [ ] `./run.sh --include-default` 可以包含默认输入

---

## 附录：任务依赖图

```
Task 1 (models)
    ↓
Task 2 (config) ─→ Task 3 (storage)
    ↓
Task 4 (input) ─→ Task 5 (output)
    ↓
    ↓
Task 6 (remote)
    ↓
Task 7 (submitter)
    ↓
Task 8 (listener)
    ↓
Task 9 (CLI)
    ↓
Task 10 (run.sh)
```
