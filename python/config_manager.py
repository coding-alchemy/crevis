import json
import os
from pathlib import Path
from typing import List, Optional


CONFIG_TEMPLATE = {
    "api_key": "your-api-key-here",
    "provider": "volcengine",
    "model_id": "doubao-seedance-2-0-fast-260128",
    "oss": {
        "base_input_url": "",
        "base_output_url": ""
    },
    "local_output_path": "~/.crevis/outputs"
}


class ConfigManager:
    """从 ~/.config/crevis.json 读取和管理配置"""

    def __init__(self, config_path: Optional[Path] = None):
        """加载配置

        Args:
            config_path: 自定义配置文件路径，为 None 时按优先级自动查找
        """
        if config_path is None:
            config_path = self._resolve_config_path()

        self.config_path = Path(config_path)
        self._config = self._load()

    def _resolve_config_path(self) -> Path:
        """按优先级解析配置文件路径"""
        # 1. 环境变量
        env_path = os.environ.get("CREVIS_CONFIG_PATH")
        if env_path:
            return Path(env_path).expanduser()

        # 2. 默认路径
        return Path.home() / ".config" / "crevis.json"

    def _load(self) -> dict:
        """加载配置文件，不存在时生成模板"""
        if not self.config_path.exists():
            self._create_template()
            raise FileNotFoundError(
                f"配置文件不存在，已生成模板: {self.config_path}\n"
                f"请编辑后重新运行。"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _create_template(self) -> None:
        """生成配置文件模板"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(CONFIG_TEMPLATE, f, indent=2, ensure_ascii=False)

    def validate(self) -> List[str]:
        """验证配置完整性，返回错误列表（空列表表示有效）"""
        errors = []
        required_fields = [
            ("api_key", "API Key"),
            ("provider", "模型提供方"),
            ("model_id", "模型 ID"),
        ]

        for field, name in required_fields:
            if not self._config.get(field):
                errors.append(f"{name}（{field}）未配置")

        # OSS 配置可选，但如果没有配置，远程化会失败
        # 这里仅做警告，不阻断
        if not self.oss_base_input_url:
            errors.append("警告：未配置 oss.base_input_url，远程化功能不可用")
        if not self.oss_base_output_url:
            errors.append("警告：未配置 oss.base_output_url，输出下载功能可能受限")

        return errors

    @property
    def api_key(self) -> str:
        return self._config.get("api_key", "")

    @property
    def provider(self) -> str:
        return self._config.get("provider", "")

    @property
    def model_id(self) -> str:
        return self._config.get("model_id", "")

    @property
    def oss_base_input_url(self) -> str:
        return self._config.get("oss", {}).get("base_input_url", "")

    @property
    def oss_base_output_url(self) -> str:
        return self._config.get("oss", {}).get("base_output_url", "")

    @property
    def local_output_path(self) -> Path:
        """本地输出存储路径（用户可配置，默认 ~/.crevis/outputs）"""
        path = self._config.get("local_output_path", "~/.crevis/outputs")
        return Path(path).expanduser()

    def get_full_config(self) -> dict:
        """获取完整配置字典（用于调试）"""
        return self._config.copy()
