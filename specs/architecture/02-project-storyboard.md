# 项目与分镜模块

> 上级文档：[Crevis 项目架构规格说明](../architecture.md)

## 1. 模块目标

本模块管理长视频创作上下文、分镜脚本、分镜修订、关键帧、候选片段和镜间连续性。它回答“要创作什么”和“哪些结果已被批准”，不直接执行模型 API。

## 2. 领域模型

### 2.1 Project

| 字段 | 说明 |
|---|---|
| `id`, `workspace_id` | 身份和隔离 |
| `name`, `description` | 项目信息 |
| `target_ratio`, `resolution`, `fps` | 统一输出规格 |
| `style_bible` | 色彩、摄影、角色和禁用元素等约束 |
| `status` | `draft/active/archived` |

`style_bible` 应是版本化结构化数据，至少包含：

- 视觉风格、色板和光线；
- 摄影机语言和镜头节奏；
- 人物及其不可变特征；
- 场景、时代和世界观；
- 禁止内容和负面提示；
- 音乐、旁白和声音原则。

### 2.2 Storyboard / StoryboardRevision

`Storyboard` 是逻辑分镜脚本，`StoryboardRevision` 保存一次不可变快照。用户或 LLM 修改后创建新修订版；工作流只能绑定已发布修订版。

状态建议：

```text
draft → in_review → published → superseded
```

### 2.3 Shot / ShotRevision

`Shot` 是分镜稳定身份，保存所属 Storyboard 和可插入排序的 `sort_key`。`ShotRevision` 保存：

- 画面描述、动作、镜头语言、对白、时长和节奏；
- 人物、声音、场景、道具引用；
- 原始提示词和已批准提示词修订；
- 首帧、目标尾帧、候选视频、已批准视频和实际尾帧；
- 连续性约束、质量检查和审批记录；
- `supersedes_id`、创建者和创建时间。

已被运行引用的修订版不得原地修改。

### 2.4 ContinuityLink

`ContinuityLink` 显式记录相邻镜头关系：

| 字段 | 说明 |
|---|---|
| `from_shot_revision_id` | 上游分镜修订 |
| `to_shot_revision_id` | 下游分镜修订 |
| `source_last_frame_version_id` | 上游已批准视频的实际尾帧 |
| `target_start_frame_version_id` | 下游首帧 |
| `constraints` | 人物、服装、场景、光线、运动方向等软约束 |
| `status` | `valid/stale/overridden` |

## 3. 从脚本创建分镜

```text
创意/脚本
  → LLM 输出符合 Schema 的 StoryboardDraft
  → 创建 StoryboardRevision 和 ShotRevision 列表
  → 用户调整顺序、时长、描述和素材引用
  → 校验总时长、必需素材和项目规格
  → 发布 StoryboardRevision
```

LLM 输出只是草稿，发布前必须可人工编辑。结构化结果至少包含分镜标题、画面、动作、镜头、对白、时长、人物、场景和与上一镜的连续性要求。

## 4. 分镜持续生成

每个分镜按以下顺序执行：

1. 加载 `ShotRevision`、项目风格圣经和人物/场景/声音 profile；
2. 确定首帧：第一镜由用户选择或生成，后续镜默认引用上一镜实际尾帧；
3. 生成目标尾帧；模型原生支持尾帧条件时直接传入，否则作为质检目标；
4. 优化结构化视频提示词；
5. 生成一个或多个候选片段；
6. 做媒体技术检查和可选语义连续性检查；
7. 用户批准候选，或修改提示词/关键帧后创建新候选；
8. 从批准片段抽取实际尾帧，建立下一条 `ContinuityLink`。

质量模型只提供分数和警告，不能替代用户的创意判断。

## 5. 连续性策略

### 5.1 硬约束

- 后一镜首帧引用前一镜已批准视频的实际尾帧；
- 关键帧和参考资产使用不可变 `AssetVersion`；
- 工作流保存边界引用，不只把描述写进提示词。

### 5.2 软约束

- 人物身份、服装、发型和道具；
- 场景位置、时段、天气、光线和色板；
- 摄影机方向、景别、焦段和运动趋势；
- 动作、视线和主体屏幕位置。

软约束进入 prompt context，也进入可选质量检查。

### 5.3 串行与并行

默认串行：当前镜批准并抽取实际尾帧后，下一镜才运行。这是连续性优先的安全模式。

仅当用户预先锁定所有边界关键帧时，片段可并行生成。并行模式必须在运行创建时明确选择，并展示连续性风险。

### 5.4 上游变更

重新批准某镜的新候选后：

1. 抽取新的实际尾帧；
2. 对比旧边界素材；
3. 将直接下游 `ContinuityLink` 和依赖节点标记为 `stale`；
4. 计算后续影响范围；
5. 由用户选择保留现有结果、只重跑下一镜或从下一镜继续重跑。

系统不得静默删除或覆盖已生成的下游结果。

## 6. 审批与候选

一个 ShotRevision 可关联多个候选视频。候选状态：

```text
generated → inspected → approved
                      └→ rejected
```

审批记录保存操作者、时间、备注、所见提示词/关键帧版本和质量检查结果。批准新的候选不会删除旧候选。

人工审批节点可以配置为：

- 每个分镜都审批；
- 仅质量检查低于阈值时审批；
- 全自动生成后集中审批；
- 使用预算或失败次数触发审批。

## 7. API

```text
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
POST   /api/v1/projects/{id}/storyboards
POST   /api/v1/storyboards/{id}/revisions
GET    /api/v1/storyboard-revisions/{id}
POST   /api/v1/storyboard-revisions/{id}:publish
POST   /api/v1/shots/{id}/revisions
POST   /api/v1/shot-revisions/{id}:generate
POST   /api/v1/shot-candidates/{id}:approve
POST   /api/v1/shot-candidates/{id}:reject
GET    /api/v1/shot-revisions/{id}/impact
```

## 8. 验收标准

- 可从脚本创建、编辑并发布分镜修订版；
- 工作流绑定不可变的 StoryboardRevision 和 ShotRevision；
- 每镜可保存多个候选和完整审批历史；
- 相邻镜头存在可查询的尾帧到首帧关系；
- 上游候选变更会标记下游影响，但不删除旧结果；
- 默认串行执行，只有锁定边界帧后才能安全并行；
- 分镜板可展示首帧、目标尾帧、实际尾帧、候选和连续性状态。
