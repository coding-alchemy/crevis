import urllib.request
from pathlib import Path
from typing import List, Optional
from models import InputItem


class RemoteUploader:
    """输入远程化：将本地文件转换为远程可访问 URL"""

    def __init__(self, base_input_url: Optional[str] = None):
        """初始化上传器

        Args:
            base_input_url: 远程输入存储基础 URL（如 OSS 前缀）
        """
        self.base_input_url = base_input_url.rstrip("/") if base_input_url else None

    def remoteize(self, version: str, input_list: List[InputItem]) -> List[InputItem]:
        """将本地输入转换为远程 URL

        Args:
            version: 版本号
            input_list: 输入列表（包含 local_path）

        Returns:
            更新后的输入列表（填充 remote_url）
        """
        if not self.base_input_url:
            raise ValueError(
                "未配置远程输入存储（oss.base_input_url），\n"
                "请在 ~/.config/crevis.json 中配置：\n"
                '  "oss": {\n'
                '    "base_input_url": "https://your-bucket.com/inputs"\n'
                "  }"
            )

        updated = []
        for item in input_list:
            if item.remote_url:
                # 已经是 URL，不需要处理
                updated.append(item)
                continue

            local_path = Path(item.local_path)
            if not local_path.exists():
                # 文件不存在时跳过，仅构建 URL
                pass

            # 构建远程 URL
            # 格式：{base_url}/versions/{version}/{type}/filename
            filename = local_path.name
            remote_url = f"{self.base_input_url}/versions/{version}/{item.type}s/{filename}"

            # 创建新的 InputItem（不可变更新）
            updated.append(InputItem(
                id=item.id,
                type=item.type,
                source=item.source,
                local_path=item.local_path,
                remote_url=remote_url,
            ))

        return updated

    def build_remote_url(self, version: str, item: InputItem) -> str:
        """构建单个文件的远程 URL（不实际上传）"""
        if not self.base_input_url:
            raise ValueError("未配置远程输入存储")

        local_path = Path(item.local_path)
        filename = local_path.name
        return f"{self.base_input_url}/versions/{version}/{item.type}s/{filename}"
