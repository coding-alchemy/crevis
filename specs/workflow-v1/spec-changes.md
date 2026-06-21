基于原始需求，在 spec 实施过程中对以下模块进行了补充和简化：

1. 配置模块：
1.1 从~/.config/crevis.json中读取配置，包括API Key、模型提供方、model id、oss.base_input_url、oss.base_output_url、local_output_path
1.2 删除prompt字段，提示词每次提交时由前端传入
1.3 删除generation字段（generate_audio、ratio、watermark、duration），这些参数每次提交时由前端传入；其中duration从prompt文本中自动提取（正则匹配"duration: 5"或"5秒"格式），默认5秒
1.4 删除input_base_path字段，本地输入不再依赖固定目录
1.5 output_base_path改为显式命名的local_output_path，用户可配置，默认~/.crevis/outputs

2. 输入模块：
2.1 删除本地输入目录结构（default/和versions/），输入不再依赖本地文件系统
2.2 用户通过前端网页直接上传文件或传入URL，后端接收文件路径列表后构建输入
2.3 InputItem删除source字段（不再区分default/version），输入来源统一为用户上传
2.4 删除"导入默认"功能，不再从本地目录读取默认素材

3. 输出模块：
3.1 输出基础路径使用local_output_path（用户可配置），默认~/.crevis/outputs
3.2 版本输出目录结构保持不变：{local_output_path}/versions/{version}/

4. 提交任务：
4.1 submit()接口参数调整：接收prompt、input_files（用户传入的文件路径列表）、generation_params（前端传入的生成参数）
4.2 不再创建本地输入目录，直接从input_files构建输入列表
4.3 watermark默认值由true改为false（不添加水印）
4.4 duration从prompt文本中提取，不再由前端显式传入

5. 响应监听模块：无变更