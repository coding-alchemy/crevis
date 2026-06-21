import shutil
from pathlib import Path
from typing import List
from models import InputItem


# 素材类型到子目录的映射
TYPE_DIRS = {
    "image": "images",
    "video": "videos",
    "audio": "audios",
}

# 支持的文件扩展名
VALID_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "video": {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"},
    "audio": {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"},
}


def _infer_type(file_path: Path) -> str:
    """根据文件扩展名推断素材类型"""
    ext = file_path.suffix.lower()
    for media_type, extensions in VALID_EXTENSIONS.items():
        if ext in extensions:
            return media_type
    raise ValueError(f"不支持的文件格式: {ext}")


class InputManager:
    """管理输入素材（用户从网页传入，不依赖本地目录）"""

    def create_items(self, files: List[Path]) -> List[InputItem]:
        """根据传入的文件路径创建输入列表

        Args:
            files: 用户传入的文件路径列表（本地文件或 URL）

        Returns:
            输入条目列表
        """
        items = []
        for file_path in files:
            file_path = Path(file_path)
            
            # 如果是 URL，直接标记为远程
            if str(file_path).startswith(("http://", "https://")):
                items.append(InputItem(
                    id=str(hash(str(file_path))),
                    type="unknown",  # URL 类型无法自动推断
                    source="version",
                    local_path=str(file_path),
                    remote_url=str(file_path),
                ))
                continue
            
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")

            media_type = _infer_type(file_path)
            items.append(InputItem(
                id=str(hash(str(file_path))),
                type=media_type,
                source="version",
                local_path=str(file_path),
            ))

        return items

    def remove_input(self, item: InputItem) -> None:
        """移除输入条目（仅清理引用，不删除实际文件）"""
        # 用户从前端传入的文件，不删除本地文件
        pass
