import os
import webbrowser
from pathlib import Path
from typing import Optional, List


class PreviewGenerator:
    """Seedance 2.0 视频编辑任务预览页面生成器

    生成 HTML 预览页面，包含多素材展示、提示词输入框、提交按钮和输出区域。
    支持实时轮询任务状态，完成后显示结果。
    """

    def __init__(
        self,
        image_paths: List[str],
        video_paths: List[str],
        audio_paths: Optional[List[str]] = None,
        server_port: int = 8765,
        output_path: Optional[str] = None,
    ):
        """初始化预览页面生成器

        Args:
            image_paths: 输入图片素材路径列表（URL 或本地路径）
            video_paths: 输入视频素材路径列表（URL 或本地路径）
            audio_paths: 输入音频素材路径列表（可选，URL 或本地路径）
            server_port: 本地服务器端口，用于接收提交请求和状态查询
            output_path: HTML 文件输出路径，默认保存到同目录的 preview.html
        """
        self.image_paths = image_paths or []
        self.video_paths = video_paths or []
        self.audio_paths = audio_paths or []
        self.server_port = server_port

        if output_path is None:
            self.output_path = Path(__file__).parent / "preview.html"
        else:
            self.output_path = Path(output_path)

    def _generate_media_boxes(self, paths: List[str], media_type: str, tag: str) -> str:
        """生成素材展示区域 HTML

        Args:
            paths: 素材路径列表
            media_type: 素材类型（图片/视频/音频）
            tag: HTML 标签（img/video/audio）

        Returns:
            HTML 字符串
        """
        if not paths:
            return f"""
        <div class="media-box">
            <h3>输入{media_type}</h3>
            <div class="placeholder">未配置</div>
        </div>"""

        boxes = []
        for i, path in enumerate(paths, 1):
            if tag == 'img':
                element = f'<img src="{path}" alt="输入{media_type} {i}" onerror="this.parentElement.innerHTML=\'<h3>输入{media_type} {i}</h3><div class=\'placeholder\'>加载失败</div>\'">'
            elif tag == 'video':
                element = f'<video src="{path}" controls autoplay loop muted onerror="this.parentElement.innerHTML=\'<h3>输入{media_type} {i}</h3><div class=\'placeholder\'>加载失败</div>\'"></video>'
            else:  # audio
                element = f'<audio src="{path}" controls onerror="this.parentElement.innerHTML=\'<h3>输入{media_type} {i}</h3><div class=\'placeholder\'>加载失败</div>\'"></audio>'

            boxes.append(f"""
        <div class="media-box">
            <h3>输入{media_type} {i}</h3>
            {element}
        </div>""")

        return "\n".join(boxes)

    def generate_html(self) -> str:
        """生成预览页面的 HTML 内容

        Returns:
            HTML 字符串
        """
        # 生成各素材展示区域
        image_boxes = self._generate_media_boxes(self.image_paths, "图片", "img")
        video_boxes = self._generate_media_boxes(self.video_paths, "视频", "video")
        audio_boxes = self._generate_media_boxes(self.audio_paths, "音频", "audio")

        # 构建路径信息字符串
        image_paths_str = "<br>".join(self.image_paths) if self.image_paths else "(空)"
        video_paths_str = "<br>".join(self.video_paths) if self.video_paths else "(空)"
        audio_paths_str = "<br>".join(self.audio_paths) if self.audio_paths else "(空)"

        # 生成 JSON 数组用于 JS
        image_paths_json = str(self.image_paths).replace("'", '"')
        video_paths_json = str(self.video_paths).replace("'", '"')
        audio_paths_json = str(self.audio_paths).replace("'", '"')

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Seedance 2.0 视频编辑任务 - 素材预览</title>
    <style>
        body {{ font-family: sans-serif; margin: 40px; background: #f5f5f5; max-width: 1000px; margin: 40px auto; }}

        /* 素材展示区域 */
        .media-section {{ margin-bottom: 20px; }}
        .media-section-title {{ color: #1976d2; font-size: 16px; margin-bottom: 10px; font-weight: bold; }}
        .media-container {{ display: flex; gap: 15px; flex-wrap: wrap; justify-content: flex-start; }}
        .media-box {{
            background: white;
            padding: 12px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
            min-width: 200px;
            max-width: 300px;
            flex: 1;
        }}
        .media-box h3 {{ margin-top: 0; color: #333; font-size: 14px; margin-bottom: 8px; }}
        .media-box img, .media-box video {{
            max-width: 100%;
            max-height: 250px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .media-box audio {{ width: 100%; }}
        .placeholder {{
            color: #999;
            padding: 30px 15px;
            font-size: 14px;
            background: #fafafa;
            border-radius: 4px;
            border: 1px dashed #ddd;
        }}

        /* 路径信息 */
        .info-box {{ background: white; padding: 12px 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); font-size: 13px; }}
        .info-box h3 {{ margin-top: 0; color: #1976d2; font-size: 16px; }}
        .info-item {{ padding: 5px 0; color: #666; }}
        .info-item .label {{ font-weight: bold; color: #333; }}
        .path-value {{ color: #1976d2; font-family: monospace; font-size: 12px; }}

        /* 提示词输入 */
        .prompt-box {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin-bottom: 20px; font-size: 18px; }}
        .prompt-box label {{ display: block; margin-bottom: 8px; font-weight: bold; }}
        .prompt-box textarea {{
            width: 100%;
            min-height: 100px;
            padding: 12px;
            border: 1px solid #90caf9;
            border-radius: 4px;
            font-size: 16px;
            font-family: sans-serif;
            resize: vertical;
            box-sizing: border-box;
        }}
        .prompt-box textarea:focus {{
            outline: none;
            border-color: #1976d2;
            box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2);
        }}
        .hint {{ color: #666; font-size: 14px; margin-top: 8px; }}

        /* 输出区域 */
        .output-box {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #1976d2;
        }}
        .output-box h3 {{
            margin-top: 0;
            color: #1976d2;
            font-size: 18px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .output-box .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            color: white;
            background: #999;
        }}
        .output-box .status-badge.idle {{ background: #999; }}
        .output-box .status-badge.running {{ background: #ff9800; }}
        .output-box .status-badge.succeeded {{ background: #4caf50; }}
        .output-box .status-badge.failed {{ background: #f44336; }}
        .output-box .status-message {{
            color: #666;
            font-size: 14px;
            margin: 10px 0;
            padding: 10px;
            background: #f5f5f5;
            border-radius: 4px;
        }}
        .output-box .video-result {{
            margin-top: 15px;
            padding: 15px;
            background: #e8f5e9;
            border-radius: 8px;
            border: 1px solid #a5d6a7;
        }}
        .output-box .video-result h4 {{
            margin-top: 0;
            color: #2e7d32;
            font-size: 16px;
        }}
        .output-box .video-url {{
            word-break: break-all;
            font-family: monospace;
            font-size: 13px;
            color: #1976d2;
            background: white;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #ddd;
            margin: 8px 0;
        }}
        .output-box .download-btn {{
            display: inline-block;
            padding: 10px 20px;
            background: #4caf50;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
            margin-top: 8px;
            transition: background 0.3s;
        }}
        .output-box .download-btn:hover {{ background: #45a049; }}
        .output-box .output-hint {{
            color: #666;
            font-size: 12px;
            margin-top: 8px;
        }}
        .output-box .error-message {{
            color: #c62828;
            font-size: 14px;
            padding: 10px;
            background: #ffebee;
            border-radius: 4px;
            border: 1px solid #ef9a9a;
        }}

        /* 提交按钮 */
        .submit-area {{ text-align: center; margin-top: 30px; }}
        .submit-btn {{
            background: #1976d2;
            color: white;
            border: none;
            padding: 15px 50px;
            font-size: 18px;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.3s;
        }}
        .submit-btn:hover {{ background: #1565c0; }}
        .submit-btn:disabled {{
            background: #90a4ae;
            cursor: not-allowed;
        }}
        .status-msg {{
            margin-top: 15px;
            font-size: 16px;
            color: #1976d2;
            min-height: 24px;
        }}
    </style>
</head>
<body>
    <h2>Seedance 2.0 视频编辑任务</h2>

    <div class="info-box">
        <h3>输入素材路径</h3>
        <div class="info-item">
            <span class="label">图片:</span><br>
            <span class="path-value">{image_paths_str}</span>
        </div>
        <div class="info-item">
            <span class="label">视频:</span><br>
            <span class="path-value">{video_paths_str}</span>
        </div>
        <div class="info-item">
            <span class="label">音频:</span><br>
            <span class="path-value">{audio_paths_str}</span>
        </div>
    </div>

    <div class="media-section">
        <div class="media-section-title">输入图片</div>
        <div class="media-container">
{image_boxes}
        </div>
    </div>

    <div class="media-section">
        <div class="media-section-title">输入视频</div>
        <div class="media-container">
{video_boxes}
        </div>
    </div>

    <div class="media-section">
        <div class="media-section-title">输入音频</div>
        <div class="media-container">
{audio_boxes}
        </div>
    </div>

    <div class="prompt-box">
        <label for="prompt-input">提示词：</label>
        <textarea id="prompt-input" placeholder="请输入视频编辑提示词（例如：将视频1礼盒中的香水替换成图片1中的面霜，运镜不变）"></textarea>
        <div class="hint">提示：确认提示词后点击底部提交按钮</div>
    </div>

    <div class="submit-area">
        <button id="submit-btn" class="submit-btn" onclick="submitData()">提交</button>
        <div id="status-msg" class="status-msg"></div>
    </div>

    <!-- 输出区域 -->
    <div class="output-box" id="output-box">
        <h3>
            输出结果
            <span class="status-badge idle" id="status-badge">等待提交</span>
        </h3>
        <div class="status-message" id="status-message">
            请在上方编辑提示词并点击提交，任务将在后台运行，状态会在此显示
        </div>
        <div id="video-result" style="display: none;">
            <div class="video-result">
                <h4>🎉 视频生成完成！</h4>
                <div>
                    <strong>视频 URL：</strong>
                    <div class="video-url" id="video-url"></div>
                </div>
                <a href="#" id="download-btn" class="download-btn" target="_blank">打开视频链接</a>
                <div class="output-hint" id="output-hint"></div>
            </div>
        </div>
        <div id="error-result" style="display: none;">
            <div class="error-message" id="error-message"></div>
        </div>
    </div>

    <script>
    let pollingInterval = null;

    async function submitData() {{
        const prompt = document.getElementById('prompt-input').value.trim();
        const imagePaths = {image_paths_json};
        const videoPaths = {video_paths_json};
        const audioPaths = {audio_paths_json};

        if (prompt.length < 2) {{
            alert('提示词太短，至少输入2个字');
            return;
        }}

        const btn = document.getElementById('submit-btn');
        const statusMsg = document.getElementById('status-msg');
        btn.disabled = true;
        statusMsg.textContent = '正在提交...';

        // 更新输出区域状态
        updateOutputStatus('running', '任务已提交，正在创建...');

        const data = {{
            prompt: prompt,
            image_paths: imagePaths,
            video_paths: videoPaths,
            audio_paths: audioPaths
        }};

        try {{
            const response = await fetch('http://localhost:{self.server_port}/submit', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(data)
            }});

            if (response.ok) {{
                statusMsg.textContent = '✅ 提交成功！任务正在后台运行';
                statusMsg.style.color = '#2e7d32';
                // 开始轮询状态
                startPolling();
            }} else {{
                statusMsg.textContent = '❌ 提交失败，请检查终端是否正常运行';
                statusMsg.style.color = '#c62828';
                btn.disabled = false;
                updateOutputStatus('failed', '提交失败，请检查终端是否正常运行');
            }}
        }} catch (e) {{
            console.error('提交失败:', e);
            statusMsg.textContent = '❌ 提交失败，请检查终端是否正常运行';
            statusMsg.style.color = '#c62828';
            btn.disabled = false;
            updateOutputStatus('failed', '提交失败: ' + e.message);
        }}
    }}

    function updateOutputStatus(status, message) {{
        const badge = document.getElementById('status-badge');
        const statusMessage = document.getElementById('status-message');
        const videoResult = document.getElementById('video-result');
        const errorResult = document.getElementById('error-result');

        // 更新状态徽章
        badge.className = 'status-badge ' + status;
        switch(status) {{
            case 'idle':
                badge.textContent = '等待提交';
                break;
            case 'running':
                badge.textContent = '生成中';
                break;
            case 'succeeded':
                badge.textContent = '已完成';
                break;
            case 'failed':
                badge.textContent = '失败';
                break;
        }}

        statusMessage.textContent = message;

        // 隐藏结果区域
        if (status !== 'succeeded') {{
            videoResult.style.display = 'none';
        }}
        if (status !== 'failed') {{
            errorResult.style.display = 'none';
        }}
    }}

    function showVideoResult(videoUrl, outputPath, outputUrl) {{
        const videoResult = document.getElementById('video-result');
        const videoUrlEl = document.getElementById('video-url');
        const downloadBtn = document.getElementById('download-btn');
        const outputHint = document.getElementById('output-hint');

        videoUrlEl.textContent = videoUrl;
        downloadBtn.href = videoUrl;
        downloadBtn.textContent = '打开视频链接';

        let hint = '';
        if (outputPath) {{
            hint += '本地路径: ' + outputPath;
        }}
        if (outputUrl) {{
            hint += (hint ? '<br>' : '') + '输出 URL: ' + outputUrl;
        }}
        if (hint) {{
            outputHint.innerHTML = hint;
        }}

        videoResult.style.display = 'block';
    }}

    function showErrorResult(message) {{
        const errorResult = document.getElementById('error-result');
        const errorMessage = document.getElementById('error-message');
        errorMessage.textContent = message;
        errorResult.style.display = 'block';
    }}

    async function startPolling() {{
        if (pollingInterval) {{
            clearInterval(pollingInterval);
        }}

        // 立即查询一次
        await checkStatus();

        // 每 3 秒轮询一次
        pollingInterval = setInterval(checkStatus, 3000);
    }}

    async function checkStatus() {{
        try {{
            const response = await fetch('http://localhost:{self.server_port}/status');
            if (!response.ok) return;

            const data = await response.json();
            console.log('任务状态:', data);

            updateOutputStatus(data.status, data.message || '处理中...');

            if (data.status === 'succeeded') {{
                showVideoResult(data.video_url, data.output_path, data.output_url);
                clearInterval(pollingInterval);
                pollingInterval = null;
            }} else if (data.status === 'failed') {{
                showErrorResult(data.message || '任务失败');
                clearInterval(pollingInterval);
                pollingInterval = null;
            }}
        }} catch (e) {{
            console.error('查询状态失败:', e);
        }}
    }}

    // 页面加载时检查状态（用于刷新页面后恢复状态）
    window.addEventListener('load', () => {{
        checkStatus();
    }});
    </script>
</body>
</html>"""

    def write_html(self, html_content: str) -> None:
        """将 HTML 内容写入到文件

        Args:
            html_content: 要写入的 HTML 字符串
        """
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def open_browser(self) -> bool:
        """使用浏览器打开预览页面

        Returns:
            是否成功打开
        """
        abs_path = os.path.abspath(self.output_path)
        return webbrowser.open(f"file://{abs_path}")

    def generate_and_open(self) -> bool:
        """生成预览页面并打开浏览器

        这是便捷方法，依次执行：生成 HTML -> 写入文件 -> 打开浏览器。

        Returns:
            是否成功生成并打开
        """
        try:
            html_content = self.generate_html()
            self.write_html(html_content)
            return self.open_browser()
        except Exception as e:
            print(f"自动打开预览失败: {e}")
            return False

    def get_output_path(self) -> str:
        """获取预览文件输出路径"""
        return str(self.output_path)
