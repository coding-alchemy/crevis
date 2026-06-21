import shutil
import urllib.request
from pathlib import Path
from typing import Optional


class OutputManager:
    """管理输出目录结构和结果下载"""

    def __init__(self, output_base_path: Path, project_outputs: Optional[Path] = None):
        """初始化输出管理器

        Args:
            output_base_path: 输出结果基础路径
            project_outputs: 项目本地 outputs/ 目录（兼容现有）
        """
        self.base_path = Path(output_base_path)
        self.project_outputs = project_outputs

    def create_version_output(self, version: str) -> Path:
        """创建版本输出目录，返回路径

        Args:
            version: 版本号

        Returns:
            版本输出目录路径
        """
        version_dir = self.base_path / "versions" / version
        version_dir.mkdir(parents=True, exist_ok=True)
        return version_dir

    def download_result(self, video_url: str, version: str, filename: str) -> Path:
        """下载结果到版本输出目录，同时复制到本地 outputs/

        Args:
            video_url: 远程视频 URL
            version: 版本号
            filename: 输出文件名

        Returns:
            下载后的文件路径
        """
        # 下载到版本输出目录
        version_dir = self.create_version_output(version)
        target_path = version_dir / filename

        try:
            urllib.request.urlretrieve(video_url, target_path)
        except Exception as e:
            raise RuntimeError(f"下载失败: {e}") from e

        # 复制到项目本地 outputs/（兼容现有）
        if self.project_outputs:
            self.project_outputs.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_path, self.project_outputs / filename)

        return target_path
