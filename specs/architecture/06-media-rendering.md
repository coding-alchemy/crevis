# 媒体处理与长视频合成模块

> 上级文档：[Crevis 项目架构规格说明](../architecture.md)

## 1. 模块目标

本模块将生成片段转为技术规格一致、可预览、可审核和可交付的长视频。业务层使用版本化 Timeline JSON 描述编辑意图，渲染器负责生成确定性的 FFmpeg 执行计划。

Shotstack 等视频 API 使用 JSON 描述图片、视频、标题、音频和转场在时间线上的排列：[官方文档](https://shotstack.io/docs/guide/)。Crevis 采用同类业务表达，但首版在自有 Worker 中用 FFmpeg 渲染。

## 2. 模块边界

媒体模块负责：

- ffprobe 媒体探测；
- 首尾帧、缩略图、联系表、代理和波形；
- 片段规格化；
- Timeline 校验与执行计划；
- 转场、字幕、旁白、音乐、响度和导出；
- 输出校验及素材回流。

它不决定分镜内容、不优化提示词，也不直接推进工作流状态；只通过任务结果返回素材引用和日志。

## 3. TimelineVersion

Timeline 是不可变业务描述。编辑产生新版本，RenderTask 绑定具体版本。

```json
{
  "schema_version": "1.0",
  "canvas": {"width": 1920, "height": 1080, "fps": 24},
  "tracks": [
    {
      "type": "video",
      "clips": [
        {
          "asset_version_id": "av_01",
          "start_ms": 0,
          "in_ms": 0,
          "duration_ms": 5000,
          "transition_out": {"type": "dissolve", "duration_ms": 300}
        },
        {
          "asset_version_id": "av_02",
          "start_ms": 4700,
          "in_ms": 0,
          "duration_ms": 5000
        }
      ]
    },
    {"type": "subtitle", "clips": []},
    {"type": "voice", "clips": []},
    {"type": "music", "clips": []}
  ],
  "output": {"container": "mp4", "video_codec": "h264", "audio_codec": "aac"}
}
```

Schema 版本化并校验：

- 素材存在且为 `ready`；
- `in_ms/out_ms/duration_ms` 不越界；
- 轨道重叠符合类型规则；
- 转场时长不超过相邻片段；
- 画布、帧率和输出 preset 受支持；
- 字幕、字体和音轨引用完整。

## 4. 规格化

生成供应商可能返回不同分辨率、帧率、像素格式、音频采样率和编解码参数。合成前创建派生的规范化版本，建议项目 preset 明确：

- 宽高和画面比例；
- 恒定帧率；
- 像素格式和色彩空间；
- H.264/H.265 等视频编码与 profile；
- AAC 等音频编码、采样率和声道；
- 无音轨片段的静音轨处理；
- 旋转元数据、SAR/DAR 和时间基准。

原始生成文件不被覆盖。规范化结果通过 `AssetRelation(normalize)` 连接。

## 5. 合成策略

### 5.1 快速拼接

无转场且流参数完全一致时，可使用 FFmpeg concat demuxer 避免重编码。FFmpeg 官方文档说明 concat 会按列表顺序读取文件，输入需要可拼接：[官方格式文档](https://ffmpeg.org/ffmpeg-formats.html)。

### 5.2 统一重编码

以下场景使用 filter graph：

- 溶解、淡入淡出等转场；
- 缩放、裁剪、填充或画面叠加；
- 字幕烧录、标题和水印；
- 旁白、对白、音乐混音和 ducking；
- 片段流参数不一致；
- 输出平台 preset 要求统一码率/编码。

执行计划由 Timeline 编译生成，保存计划摘要而不是把任意用户 FFmpeg 命令当业务数据。

## 6. 音频

按独立轨道处理：

- `dialogue/voice`：对白和旁白；
- `music`：背景音乐；
- `sfx`：环境和效果音；
- `source_audio`：生成片段原声。

项目 preset 定义采样率、声道、目标响度、峰值、淡入淡出和 ducking。冲突时按轨道优先级和显式 automation 处理。

## 7. 字幕和字体

- 字幕本身作为版本化素材；
- Timeline 引用字幕版本、时间偏移和样式；
- 字体必须进入素材库并记录授权；
- 同时支持烧录字幕和可选外挂字幕输出；
- 文本转义和路径处理不能拼接不受控 shell 命令。

## 8. 渲染流程

```text
创建 RenderTask
  → 校验 TimelineVersion
  → 下载/挂载输入素材
  → 复用或生成规范化片段
  → 编译 FFmpeg 执行计划
  → 执行并采集进度/日志
  → ffprobe + 最小解码校验
  → 上传对象存储
  → 创建成片 AssetVersion 和 composed_from 关系
  → RenderTask succeeded
```

临时目录按 task 隔离，成功或失败后按策略清理。渲染 Worker 必须限制 CPU、内存、磁盘和最大运行时间。

## 9. 输出校验

至少检查：

- 文件存在、非零且容器可解析；
- 视频/音频流符合 preset；
- 实际时长与 Timeline 容差一致；
- 能从头、中、尾解码抽帧；
- 没有意外全黑或完全静音区间；
- SHA-256、大小和 ffprobe 元数据已记录。

有损编码不要求输出字节级完全一致；可复现指相同 Timeline、素材版本、preset 和工具版本能解释性地产生等价输出。

## 10. 任务记录

`RenderTask`/attempt 保存：

- TimelineVersion 和输出 preset；
- FFmpeg/ffprobe 版本；
- 输入 AssetVersion 列表和校验和；
- 规范化派生版本；
- 命令/滤镜图摘要；
- 日志对象键、退出码和耗时；
- 输出 AssetVersion、校验结果和成本估计。

## 11. API

```text
POST   /api/v1/timelines
POST   /api/v1/timelines/{id}/versions
GET    /api/v1/timeline-versions/{id}
POST   /api/v1/timeline-versions/{id}:validate
POST   /api/v1/timeline-versions/{id}:render
GET    /api/v1/render-tasks/{id}
POST   /api/v1/render-tasks/{id}:cancel
```

## 12. 验收标准

- 已批准分镜可生成版本化 Timeline；
- 所有片段在合成前统一规格且保留原始文件；
- 无转场兼容输入可快速拼接；复杂编辑走统一重编码；
- 字幕、旁白、音乐和基础转场可表达并渲染；
- 成片通过媒体校验后回流素材库；
- 成片能反查 Timeline、片段、音轨、工具版本和处理日志；
- 重复渲染不覆盖旧成片；
- 不允许用户直接注入任意 FFmpeg shell 命令。
