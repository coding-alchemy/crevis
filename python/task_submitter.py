import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from volcenginesdkarkruntime import Ark
from models import Task, InputItem, PENDING
from config_manager import ConfigManager
from input_manager import InputManager
from output_manager import OutputManager
from remote_uploader import RemoteUploader
from storage import Storage


def extract_duration(prompt: str) -> int:
    """从 prompt 中提取 duration（秒），默认 5"""
    # 匹配 "duration: 5" 或 "duration=5"
    match = re.search(r"duration[:=]\s*(\d+)", prompt, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # 匹配 "5秒" 或 "5 秒"
    match = re.search(r"(\d+)\s*秒", prompt)
    if match:
        return int(match.group(1))
    return 5


class TaskSubmitter:
    """负责任务版本创建、远程化、提交和持久化"""

    def __init__(
        self,
        config: ConfigManager,
        input_mgr: InputManager,
        output_mgr: OutputManager,
        storage: Storage,
    ):
        self.config = config
        self.input_mgr = input_mgr
        self.output_mgr = output_mgr
        self.storage = storage
        self.uploader = RemoteUploader(config.oss_base_input_url)
        self._submitted_versions: set = set()

    def generate_version(self) -> str:
        """生成唯一版本号"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"v{timestamp}"

    def submit(
        self,
        prompt: str,
        input_files: List[Path],
        generation_params: Dict[str, Any],
        include_default: bool = False,
    ) -> Task:
        """提交任务

        Args:
            prompt: 提示词（包含 duration 信息）
            input_files: 用户传入的输入文件路径列表
            generation_params: 生成参数（必须包含 generate_audio, ratio, watermark）
            include_default: 是否包含默认输入（当前不使用，保留接口）

        Returns:
            Task 对象
        """
        # 1. 生成版本号
        version = self.generate_version()
        if version in self._submitted_versions:
            raise RuntimeError(f"版本 {version} 已提交，不允许重复提交")

        # 2. 创建版本输出目录（输入不依赖本地目录）
        self.output_mgr.create_version_output(version)

        # 3. 构建输入列表（从用户传入的文件）
        input_list = self.input_mgr.create_items(input_files)

        # 4. 远程化输入
        remote_inputs = self.uploader.remoteize(version, input_list)

        # 5. 构建 API 请求参数
        # 从 prompt 中提取 duration
        duration = extract_duration(prompt)
        generation_params["duration"] = duration
        
        content_items = self._build_content(prompt, remote_inputs)

        # 6. 提交 API 任务
        client = Ark(api_key=self.config.api_key)
        create_result = client.content_generation.tasks.create(
            model=self.config.model_id,
            content=content_items,
            **generation_params,
        )
        task_id = create_result.id

        # 7. 收集任务信息
        output_path = str(self.output_mgr.base_path / "versions" / version)
        request_params = self._build_request_params(
            self.config.model_id, content_items, generation_params
        )

        task = Task(
            task_id=task_id,
            version=version,
            model_id=self.config.model_id,
            input_list=remote_inputs,
            output_path=output_path,
            request_params=request_params,
            status=PENDING,
        )

        # 8. 持久化
        self.storage.save_task(task)

        # 9. 标记已提交
        self._submitted_versions.add(version)

        return task

    def _build_content(self, prompt: str, inputs: List[InputItem]) -> List[Dict[str, Any]]:
        """构建 API content 列表"""
        content = [
            {
                "type": "text",
                "text": prompt,
            }
        ]

        for item in inputs:
            if not item.remote_url:
                raise ValueError(f"输入未远程化: {item.local_path}")

            if item.type == "image":
                content.append({
                    "type": "image_url",
                    "image_url": {"url": item.remote_url},
                    "role": "reference_image",
                })
            elif item.type == "video":
                content.append({
                    "type": "video_url",
                    "video_url": {"url": item.remote_url},
                    "role": "reference_video",
                })
            elif item.type == "audio":
                content.append({
                    "type": "audio_url",
                    "audio_url": {"url": item.remote_url},
                    "role": "reference_audio",
                })

        return content

    def _build_request_params(
        self, model_id: str, content: List[Dict[str, Any]], generation_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建请求参数（脱敏）"""
        return {
            "model": model_id,
            "content": content,
            "generate_audio": generation_params.get("generate_audio", True),
            "ratio": generation_params.get("ratio", "16:9"),
            "duration": generation_params.get("duration", 5),
            "watermark": generation_params.get("watermark", True),
            "api_key": "api_key",  # 脱敏
        }
