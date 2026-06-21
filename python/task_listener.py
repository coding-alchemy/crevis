import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from volcenginesdkarkruntime import Ark
from models import Task, SUCCEEDED, FAILED, COMPLETED, TIMEOUT, PENDING, RUNNING
from config_manager import ConfigManager
from output_manager import OutputManager
from storage import Storage


class TaskListener:
    """异步监听任务状态，完成后下载结果"""

    # 轮询间隔（秒）
    POLL_INTERVAL = 30
    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 30 * 60  # 30 分钟

    def __init__(
        self,
        config: ConfigManager,
        output_mgr: OutputManager,
        storage: Storage,
    ):
        self.config = config
        self.output_mgr = output_mgr
        self.storage = storage
        self._client = Ark(api_key=config.api_key)

    def start_listening(self, task: Task, timeout: Optional[int] = None) -> None:
        """启动对指定任务的监听（后台线程）

        Args:
            task: 要监听的任务
            timeout: 超时时间（秒），默认 30 分钟
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        thread = threading.Thread(
            target=self._listen,
            args=(task, timeout),
            daemon=True,
        )
        thread.start()

    def _listen(self, task: Task, timeout: int) -> None:
        """监听循环"""
        deadline = datetime.now() + timedelta(seconds=timeout)

        while datetime.now() < deadline:
            try:
                result = self.poll_status(task.task_id)
                status = result.status

                if status == SUCCEEDED:
                    self.on_succeeded(task, result.content.video_url)
                    return
                elif status == FAILED:
                    self.on_failed(task, result.error)
                    return
                elif status in (PENDING, RUNNING):
                    # 继续等待
                    self.storage.update_task_status(task.task_id, status)

            except Exception as e:
                # 轮询异常，记录但不终止
                print(f"轮询异常: {e}")

            time.sleep(self.POLL_INTERVAL)

        # 超时
        self.on_timeout(task)

    def poll_status(self, task_id: str):
        """轮询一次任务状态

        Args:
            task_id: 任务 ID

        Returns:
            API 响应对象
        """
        return self._client.content_generation.tasks.get(task_id=task_id)

    def on_succeeded(self, task: Task, video_url: str) -> None:
        """任务成功回调"""
        print(f"\n任务 {task.task_id} 已完成！")
        print(f"视频 URL: {video_url}")

        try:
            # 下载结果
            filename = f"seedance_{task.task_id}.mp4"
            output_path = self.output_mgr.download_result(
                video_url, task.version, filename
            )
            print(f"结果已下载到: {output_path}")

            # 更新状态
            self.storage.update_task_status(task.task_id, COMPLETED)

        except Exception as e:
            print(f"下载失败: {e}")
            print(f"视频 URL: {video_url}")
            self.storage.update_task_status(task.task_id, SUCCEEDED)

    def on_failed(self, task: Task, error: str) -> None:
        """任务失败回调"""
        print(f"\n任务 {task.task_id} 失败: {error}")
        self.storage.update_task_status(task.task_id, FAILED, error_message=error)

    def on_timeout(self, task: Task) -> None:
        """任务超时回调"""
        print(f"\n任务 {task.task_id} 轮询超时")
        self.storage.update_task_status(task.task_id, TIMEOUT)
