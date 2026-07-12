# 实施路线与测试策略

> 上级文档：[Crevis 项目架构规格说明](../architecture.md)

## 1. 目标

本文件将目标架构转化为渐进式实施顺序。原则是先闭合数据谱系和恢复能力，再增加可视化编排、多供应商和并行化。

## 2. 推荐包结构

```text
crevis/
├── app/
│   ├── api/                    # FastAPI 路由、schema、鉴权
│   ├── domain/                 # 实体、状态机和策略；不依赖 SDK
│   │   ├── assets/
│   │   ├── projects/
│   │   ├── prompts/
│   │   ├── generations/
│   │   ├── workflows/
│   │   └── timelines/
│   ├── application/            # 用例与事务编排
│   ├── infrastructure/
│   │   ├── db/                 # repository、migration、outbox
│   │   ├── queue/
│   │   ├── storage/
│   │   ├── providers/
│   │   │   ├── llm/
│   │   │   ├── image/
│   │   │   ├── video/
│   │   │   └── audio/
│   │   └── media/
│   ├── workers/
│   └── settings.py
├── web/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── e2e/
├── specs/
└── python/                     # 迁移期间 legacy，最终删除
```

领域层不得 import Ark、Redis、ORM 或 FFmpeg 封装。外部能力通过 Protocol/Port 注入。

## 3. Phase 0：收敛现有链路

工作：

- 选定 `main.py` 链路为迁移入口，`video_generator.py` 标记 legacy；
- 修复 URL 先转 `Path` 导致的识别问题；
- 用真实对象存储上传替换 `RemoteUploader` 的 URL 拼接；
- ID 改为 UUIDv7/ULID，展示版本与主键分离；
- 配置校验区分 error 和 warning；
- 为单任务流程增加供应商 mock 和自动测试；
- 建立 Seedance 实际账号能力矩阵。

验收：单任务从上传到结果入库可重复执行；CLI 退出不影响任务；历史中没有明文密钥。

## 4. Phase 1：素材与任务底座

工作：

- 引入 PostgreSQL migration；
- 实现 Asset/AssetVersion/Relation；
- 实现 GenerationTask/Attempt 和状态事件；
- 接入 S3/MinIO、签名 URL、ffprobe 和缩略图；
- 把 Ark 调用封装为 `SeedanceVideoProvider`；
- 独立 Worker 完成提交、状态同步和结果搬运；
- 实现 Outbox、幂等和 reconciliation；
- 提供素材和任务 API。

验收：服务和 Worker 任意重启后可恢复；重复请求不重复计费；结果可追溯到输入。

## 5. Phase 2：项目、提示词与分镜

工作：

- 实现 Project、Storyboard/Revision、Shot/Revision；
- 实现 Prompt/Revision 和结构化 LLM 输出；
- 接入直接 LLM API 和可选 OpenCode CLI 适配器；
- 实现人物、声音、场景 profile；
- 前端提供项目工作台、素材库和分镜板。

验收：可从脚本生成可编辑分镜；每镜保留原始、优化和人工提示词版本。

## 6. Phase 3：持久化工作流与连续生成

工作：

- 实现 WorkflowDefinition/Version、Run 和 NodeRun；
- 实现 DAG 校验、租约、重试、暂停、取消和人工审批；
- 实现关键帧、视频生成、抽帧和质检节点；
- 实现 `shot.sequence` 复合节点；
- 实现 ContinuityLink、下游 stale 检测和选择性重跑；
- 提供运行图和事件流。

验收：至少 5 个分镜跨服务重启持续生成；相邻镜使用实际尾帧/首帧关系；失败可从节点续跑。

## 7. Phase 4：时间线与长视频导出

工作：

- 实现 Timeline Schema/Version；
- 实现规格化和 FFmpeg 渲染；
- 支持硬切、基础转场、字幕、旁白和音乐；
- 成片及派生关系回流素材库；
- 增加媒体质量、成本和性能指标。

验收：已批准分镜可稳定导出长视频；输入版本可追溯；重复渲染不覆盖历史。

## 8. Phase 5：扩展与规模化

工作：

- 多供应商路由、配额、预算、优先级和降级；
- 锁定边界帧后的安全并行生成；
- 团队评论、审批策略和工作流模板；
- 基于真实吞吐评估 Temporal/托管编排迁移；
- 多环境部署、备份恢复和容量规划。

## 9. 数据迁移

### 9.1 JSONL

提供一次性导入器：

- 将旧 Task 转为 GenerationTask；
- `input_list` 中可访问 URL 导入 AssetVersion，失效 URL 标记为 unresolved；
- 请求参数创建脱敏快照；
- 旧状态映射到新状态事件；
- 保留原始行和导入批次 ID。

### 9.2 本地 outputs

扫描旧输出，计算哈希和媒体元数据，作为 `legacy_import` AssetVersion 入库。不能仅保存旧绝对路径。

### 9.3 双链路退出

迁移期顺序：

1. 旧 CLI 改调 application service；
2. 新任务只写数据库，必要时额外导出 JSONL；
3. 验证新 UI/CLI；
4. 冻结旧 `video_generator.py`；
5. 删除不再使用的配置和模块。

## 10. 测试策略

### 10.1 单元测试

- 状态机和非法转换；
- DAG 无环和端口类型；
- 幂等键和请求指纹；
- Prompt Schema 和上下文哈希；
- 连续性 stale 传播；
- Timeline 时间和转场计算。

### 10.2 集成测试

- PostgreSQL 事务、唯一约束和 Outbox；
- Redis 重复投递和延迟任务；
- MinIO 上传、签名和对象不存在；
- ffprobe/FFmpeg 规格化与渲染；
- webhook 验签与重复事件。

### 10.3 供应商契约测试

所有 VideoProvider 对同一归一化状态集合表现一致。真实供应商测试使用小额受控账号，并与 mock 测试分开。

### 10.4 故障注入

- 提交超时但供应商已受理；
- 重复/乱序 webhook；
- Worker 在副作用前后被杀；
- 租约过期和旧 Worker 回写；
- 结果下载中断；
- 数据库/对象存储短暂失败；
- FFmpeg 进程超时和磁盘不足。

### 10.5 端到端

固定场景：3 个分镜，其中一个候选被拒并重生成；中途重启 API/Worker；最终合成长视频并验证完整谱系。

### 10.6 媒体黄金样例

固定输入验证时长、分辨率、帧率、音轨、边界帧和 Timeline。由于有损编码，不要求输出字节完全相同。

### 10.7 安全测试

SSRF、伪造 MIME、超大文件、越权素材引用、签名 URL 过期、命令注入和日志密钥泄露。

## 11. 发布门禁

每个 Phase 至少满足：

- migration 可前滚并有恢复方案；
- 新增状态机有非法转换测试；
- 外部副作用有幂等和故障测试；
- API Schema/OpenAPI 更新；
- 指标、告警和操作手册齐备；
- 不引入新的明文密钥或本地绝对路径持久化；
- 文档与实现差异被记录为显式 ADR/issue。

## 12. 待确认事项

1. 首批对象存储是火山 TOS、阿里 OSS 还是通用 S3；领域接口仍保持 S3 风格。
2. Seedance 当前账号实际支持的首帧、尾帧、参考音频、时长和 webhook 能力。
3. 第一版是否需要多人 Workspace。
4. LLM 生产调用使用直接 API 还是 OpenCode CLI；建议 CLI 仅用于本地/受控单机。
5. 质量检查首版仅做技术检查，还是加入视觉模型连续性评分。
6. 成片需要的商用响度、色彩空间、字幕格式和平台 preset。

## 13. 总体验收

- 任意成片可追溯 Timeline、分镜、关键帧、提示词、模型调用和原始素材；
- 任意运行中进程重启后可恢复；
- 同一幂等请求不创建重复供应商任务；
- 供应商成功但下载失败不会重新生成；
- 素材不可变且派生关系完整；
- 工作流定义和运行状态分离；
- 相邻分镜具有明确尾帧到首帧关系；
- 合成前完成规格化，渲染配置可版本化；
- 密钥不进入业务数据、日志和前端；
- CLI 与 Web 不再维护两套业务逻辑。
