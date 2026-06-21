# 方舟视频生成 SDK 配置驱动版
#
# 基于 YAML 配置调用 Seedance 2.0 视频生成模型，所有参数从 conf/input.yaml 读取。
# 支持环境变量覆盖（ARK_API_KEY）、配置验证、可选参考音频、浏览器预览素材。
# 支持上层目录的 images/videos/outputs 作为输入/输出路径。
#
# 用法：
#   python python/video_generator.py
#   # 或
#   ./run.sh

import json
import os
import time
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from volcenginesdkarkruntime import Ark

from config_loader import ConfigLoader
from preview_generator import PreviewGenerator


class PreviewServer(BaseHTTPRequestHandler):
    """本地 HTTP 服务器，接收前端提交和状态查询"""

    def _send_cors_headers(self):
        """发送 CORS 响应头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _send_json(self, data: dict):
        """发送 JSON 响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        """处理 GET 请求（查询任务状态）"""
        if self.path == '/status':
            status = {
                'task_id': getattr(self.server, 'task_id', None),
                'status': getattr(self.server, 'task_status', 'idle'),
                'message': getattr(self.server, 'task_message', '等待提交'),
                'video_url': getattr(self.server, 'video_url', None),
                'output_path': getattr(self.server, 'output_path', None),
                'output_url': getattr(self.server, 'output_url', None),
            }
            self._send_json(status)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """处理 POST 请求（提交任务）"""
        if self.path == '/submit':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                self.server.received_data = data

            self._send_json({'status': 'ok', 'message': '任务已接收'})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """覆盖日志方法，减少控制台输出"""
        pass


def start_preview_server(port=8765):
    """启动预览服务器

    Returns:
        (server, thread) 元组
    """
    server = HTTPServer(('localhost', port), PreviewServer)
    server.received_data = None
    server.should_stop = False
    # 任务状态
    server.task_id = None
    server.task_status = 'idle'  # idle, running, succeeded, failed
    server.task_message = '等待提交'
    server.video_url = None
    server.output_path = None
    server.output_url = None

    def serve():
        while not server.should_stop:
            server.handle_request()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return server, thread


def download_video(url: str, output_path: Path) -> None:
    """下载视频到指定路径"""
    print(f"正在下载视频到: {output_path}")
    try:
        urllib.request.urlretrieve(url, output_path)
        print(f"视频已保存: {output_path}")
    except Exception as e:
        print(f"下载失败: {e}")
        print(f"视频 URL: {url}")


def run_task(server, client, config, model_id, image_urls, video_urls, audio_urls,
             generate_audio, ratio, duration, watermark, user_content):
    """在后台线程中运行任务"""
    try:
        # 更新状态
        server.task_status = 'running'
        server.task_message = '正在调用模型创建任务...'

        # 构建 content 列表
        content_items = [
            {
                "type": "text",
                "text": user_content,
            },
        ]

        # 添加所有图片
        for img_url in image_urls:
            if img_url:
                content_items.append({
                    "type": "image_url",
                    "image_url": {
                        "url": img_url
                    },
                    "role": "reference_image",
                })

        # 添加所有视频
        for vid_url in video_urls:
            if vid_url:
                content_items.append({
                    "type": "video_url",
                    "video_url": {
                        "url": vid_url
                    },
                    "role": "reference_video",
                })

        # 添加所有音频
        for aud_url in audio_urls:
            if aud_url:
                content_items.append({
                    "type": "audio_url",
                    "audio_url": {
                        "url": aud_url
                    },
                    "role": "reference_audio",
                })

        # 创建生成任务
        create_result = client.content_generation.tasks.create(
            model=model_id,
            content=content_items,
            generate_audio=generate_audio,
            ratio=ratio,
            duration=duration,
            watermark=watermark,
        )

        task_id = create_result.id
        server.task_id = task_id
        server.task_message = f'任务已创建（ID: {task_id}），正在等待生成...'
        print(f"任务创建成功！任务 ID: {task_id}")

        # 轮询并等待结果
        while True:
            get_result = client.content_generation.tasks.get(task_id=task_id)
            status = get_result.status
            server.task_status = status

            if status == "succeeded":
                video_url = get_result.content.video_url
                server.video_url = video_url
                server.task_message = '任务已完成！'

                # 下载视频到输出目录
                if video_url:
                    output_filename = f"seedance_{task_id}.mp4"
                    output_path = config.get_output_path(output_filename)
                    download_video(video_url, output_path)
                    server.output_path = str(output_path)

                    # 获取输出 URL
                    output_url = config.get_output_url(output_filename)
                    if output_url:
                        server.output_url = output_url
                        print(f"\n输出文件已保存到本地: {output_path}")
                        print(f"输出 URL: {output_url}")

                print("\n任务已完成！")
                break
            elif status == "failed":
                server.task_status = 'failed'
                server.task_message = f'任务失败: {get_result.error}'
                print(f"\n任务失败: {get_result.error}")
                break
            else:
                server.task_message = f'当前状态: {status}，正在生成中...'
                print(f"当前状态: {status}，30秒后再次查询...")
                time.sleep(30)

    except Exception as e:
        server.task_status = 'failed'
        server.task_message = f'调用失败: {e}'
        print(f"\n调用失败: {e}")


def main():
    # 加载配置
    config = ConfigLoader()

    # 验证配置
    errors = config.validate()
    if errors:
        print("\n配置验证失败，请检查 conf/input.yaml：")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        print("\n提示：")
        print("  - API Key 可以通过环境变量 ARK_API_KEY 设置")
        print("  - 其他参数请编辑 conf/input.yaml 文件")
        return

    print("------------------------------------------------------------------------------------------------------------------------------------------------------")
    print("   Seedance 2.0 视频生成 Python SDK（配置驱动版）")
    print("------------------------------------------------------------------------------------------------------------------------------------------------------")

    # 打印配置摘要
    config.print_config()
    print()

    # 1. 获取 API Key
    api_key = config.get_api_key()
    masked_key = f"...{api_key[-6:]}" if len(api_key) > 6 else "***"
    print(f"检测到 API Key (尾号: {masked_key})")

    # 2. 初始化客户端
    client = Ark(api_key=api_key)

    # 3. 读取生成参数
    model_id = config.get_model_id()

    # 获取输入素材路径列表（从配置或默认目录自动获取，已转换为 OSS URL）
    image_urls = config.get_input_image_paths()
    video_urls = config.get_input_video_paths()
    audio_urls = config.get_input_audio_paths()

    generate_audio = config.get_generate_audio()
    ratio = config.get_ratio()
    duration = config.get_duration()
    watermark = config.get_watermark()
    output_dir = config.get_output_dir()

    # 验证所有素材 URL 都是 http:// 或 https://
    invalid_urls = []
    for i, url in enumerate(image_urls):
        if url and not url.startswith(('http://', 'https://')):
            invalid_urls.append(f"图片 {i+1}: {url}")
    for i, url in enumerate(video_urls):
        if url and not url.startswith(('http://', 'https://')):
            invalid_urls.append(f"视频 {i+1}: {url}")
    for i, url in enumerate(audio_urls):
        if url and not url.startswith(('http://', 'https://')):
            invalid_urls.append(f"音频 {i+1}: {url}")

    if invalid_urls:
        print("\n❌ 错误：以下素材路径不是有效的 URL（API 只支持 http:// 或 https://）:")
        for item in invalid_urls:
            print(f"   - {item}")
        print("\n解决方案：")
        print("   1. 将本地文件上传到可访问的 URL（如对象存储）")
        print("   2. 在 conf/input.yaml 中使用 URL 而不是本地路径")
        print("   3. 或清空 inputs 配置，程序会自动从默认目录获取文件")
        return

    # 启动预览服务器
    server_port = 8765
    server, server_thread = start_preview_server(port=server_port)
    print(f"\n已启动预览服务器 (http://localhost:{server_port})")

    # 尝试自动打开浏览器预览页面
    print("正在尝试在浏览器中打开预览页面...")
    try:
        preview = PreviewGenerator(
            image_paths=image_urls,
            video_paths=video_urls,
            audio_paths=audio_urls,
            server_port=server_port,
        )
        preview.generate_and_open()
        print("预览页面已打开，请在浏览器中编辑提示词并点击提交按钮")
    except Exception as e:
        print(f"自动打开预览失败: {e}")

    # 等待用户提交
    print("\n等待用户提交...")
    print("提示：在浏览器中编辑提示词，然后点击底部的'提交'按钮")

    try:
        while server.received_data is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n用户取消操作")
        server.should_stop = True
        server_thread.join(timeout=1)
        return

    # 获取提交的数据
    submitted_data = server.received_data
    user_content = submitted_data.get('prompt', '')

    # 使用提交的数据覆盖（优先使用用户提交的，如果为空则使用配置中的）
    submitted_image_paths = submitted_data.get('image_paths', [])
    submitted_video_paths = submitted_data.get('video_paths', [])
    submitted_audio_paths = submitted_data.get('audio_paths', [])

    # 如果用户提交了新的路径，使用提交的（必须是 URL）
    if submitted_image_paths:
        image_urls = [p for p in submitted_image_paths if p.startswith(('http://', 'https://'))]
    if submitted_video_paths:
        video_urls = [p for p in submitted_video_paths if p.startswith(('http://', 'https://'))]
    if submitted_audio_paths:
        audio_urls = [p for p in submitted_audio_paths if p.startswith(('http://', 'https://'))]

    print("\n==================================================")
    print("   用户已提交，创建 seedance 2.0 视频编辑任务")
    print("==================================================")
    print(f"模型 ID   : {model_id}")
    print(f"文本提示词: {user_content}")
    print(f"输入图片  : {image_urls}")
    print(f"输入视频  : {video_urls}")
    if audio_urls:
        print(f"输入音频  : {audio_urls}")
    print(f"生成音频  : {generate_audio}")
    print(f"视频比例  : {ratio}")
    print(f"视频时长  : {duration} 秒")
    print(f"水印      : {watermark}")
    print(f"输出目录  : {output_dir}")
    print("--------------------------------------------------")

    # 在后台线程中运行任务，保持服务器运行以便前端查询状态
    task_thread = threading.Thread(
        target=run_task,
        args=(server, client, config, model_id, image_urls, video_urls, audio_urls,
              generate_audio, ratio, duration, watermark, user_content),
        daemon=True
    )
    task_thread.start()

    print("\n任务已在后台启动，请保持浏览器页面打开以查看进度")
    print("按 Ctrl+C 可以退出程序（服务器将继续运行直到任务完成）")

    try:
        # 保持主线程运行，等待任务完成或用户中断
        while task_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n用户取消操作")

    # 关闭服务器
    server.should_stop = True
    server_thread.join(timeout=1)
    server.server_close()
    print("\n预览服务器已关闭")


if __name__ == "__main__":
    main()
