import os
import copy
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List


class ConfigLoader:
    """Seedance 2.0 视频生成配置解析工具类

    支持从多级配置文件读取，并与默认配置合并。提供配置验证功能。
    支持上层目录的 images/videos/audios 作为输入/输出路径。
    支持单路径和多路径（列表）配置。

    配置优先级（从高到低）：
        1. 环境变量（ARK_API_KEY）
        2. 上层目录配置（~/.ark.yaml 或 项目父目录 .ark.yaml）
        3. 项目内配置（conf/input.yaml）
        4. 默认配置

    路径解析规则：
        - 输入的 image_paths / video_paths / audio_paths：
          支持单路径（字符串）或多路径（列表）。
          如果以 http:// 或 https:// 开头，视为 URL 直接使用；
          否则视为相对于上层目录的路径，自动解析为绝对路径。
        - 输出目录：默认为上层目录的 outputs/，可在配置中覆盖。

    用法：
        config = ConfigLoader()  # 默认加载多级配置
        config = ConfigLoader('/path/to/custom.yaml')  # 自定义项目内配置路径

        # 获取配置
        api_key = config.get_api_key()
        model_id = config.get_model_id()
        image_paths = config.get_input_image_paths()  # 返回列表
        output_dir = config.get_output_dir()  # 获取输出目录

        # 验证配置
        errors = config.validate()
        if errors:
            print(errors)
    """

    # 上层配置文件名（存放敏感信息，如 API Key，不提交到项目仓库）
    PARENT_CONFIG_NAME = '.ark.yaml'

    # 默认配置（作为 fallback）
    DEFAULT_CONFIG = {
        'api': {
            'key': '',
        },
        'model': {
            'id': 'doubao-seedance-2-0-fast-260128',
        },
        'content': {
            'prompt': '',
        },
        'inputs': {
            'image_paths': '',
            'video_paths': '',
            'audio_paths': '',
        },
        'generation': {
            'generate_audio': True,
            'ratio': '16:9',
            'duration': 5,
            'watermark': True,
        },
        'paths': {
            'image_dir': 'images',
            'video_dir': 'videos',
            'audio_dir': 'audios',
            'output_dir': 'outputs',
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """初始化配置加载器

        Args:
            config_path: 项目内配置文件路径，默认从项目根目录的 conf/input.yaml 加载
        """
        # 项目根目录（python/config_loader.py 的上两级）
        self.project_root = Path(__file__).parent.parent

        # 上层目录（项目路径的父目录）
        self.parent_dir = self.project_root.parent

        # 加载上层目录配置（~/.ark.yaml 或 项目父目录 .ark.yaml）
        self._parent_config = self._load_parent_config()

        # 加载项目内配置
        if config_path is None:
            self.config_path = self.project_root / 'conf' / 'input.yaml'
        else:
            self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_parent_config(self) -> Dict[str, Any]:
        """加载上层目录配置文件（存放 API Key 等敏感信息）

        查找顺序：
            1. 用户主目录 ~/.ark.yaml
            2. 项目父目录（项目路径的上层） .ark.yaml

        Returns:
            配置字典，如果未找到则返回空字典
        """
        config = {}

        # 1. 尝试用户主目录 ~/.ark.yaml
        home_config = Path.home() / self.PARENT_CONFIG_NAME
        if home_config.exists():
            try:
                with open(home_config, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                return config
            except Exception as e:
                print(f"警告：读取主目录配置 {home_config} 失败: {e}")

        # 2. 尝试项目父目录
        parent_config = self.project_root.parent / self.PARENT_CONFIG_NAME
        if parent_config.exists():
            try:
                with open(parent_config, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                return config
            except Exception as e:
                print(f"警告：读取父目录配置 {parent_config} 失败: {e}")

        return config

    def _load_config(self) -> Dict[str, Any]:
        """加载并合并配置（默认配置 + 项目内文件配置）

        文件配置会覆盖默认配置中对应的值。
        """
        # 深拷贝默认配置，避免修改原始默认值
        config = copy.deepcopy(self.DEFAULT_CONFIG)

        # 如果项目内配置文件存在，读取并合并
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f) or {}

                # 递归合并配置
                self._merge_config(config, file_config)
            except yaml.YAMLError as e:
                print(f"警告：项目配置解析失败: {e}")
                print(f"将使用默认配置")
            except Exception as e:
                print(f"警告：读取项目配置失败: {e}")
                print(f"将使用默认配置")

        return config

    def _merge_config(self, base: Dict, override: Dict) -> None:
        """递归合并两个字典

        override 中的值会覆盖 base 中对应的值。
        如果是嵌套字典，则递归合并；如果是其他类型，直接覆盖。
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _resolve_paths(self, paths_value) -> List[str]:
        """解析路径配置（支持单值或列表）

        Args:
            paths_value: 路径配置值（字符串、列表或空）

        Returns:
            解析后的路径列表
        """
        if not paths_value:
            return []

        # 如果是单字符串，转为列表
        if isinstance(paths_value, str):
            paths_value = [paths_value]

        # 解析每个路径
        resolved = []
        for path_str in paths_value:
            if not path_str or not str(path_str).strip():
                continue
            path_str = str(path_str).strip()

            # 如果是 URL，直接返回
            if path_str.startswith(('http://', 'https://')):
                resolved.append(path_str)
                continue

            # 如果是绝对路径，直接返回
            if Path(path_str).is_absolute():
                resolved.append(path_str)
                continue

            # 否则视为相对于上层目录的路径
            resolved.append(str((self.parent_dir / path_str).resolve()))

        return resolved

    def get_api_key(self) -> str:
        """获取 API Key

        优先级：
            1. 环境变量 ARK_API_KEY
            2. 上层配置中的 api_key 或 api.key
            3. 项目内配置中的 api.key
        """
        # 1. 环境变量
        env_key = os.environ.get('ARK_API_KEY', '')
        if env_key:
            return env_key

        # 2. 上层配置（支持两种格式：api_key 或 api.key）
        parent_key = (
            self._parent_config.get('api_key', '') or
            self._parent_config.get('api', {}).get('key', '')
        )
        if parent_key:
            return parent_key

        # 3. 项目内配置
        return self._config.get('api', {}).get('key', '')

    def get_model_id(self) -> str:
        """获取模型 ID"""
        return self._config.get('model', {}).get('id',
                                                   self.DEFAULT_CONFIG['model']['id'])

    def get_prompt(self) -> str:
        """获取文本提示词"""
        return self._config.get('content', {}).get('prompt', '')

    def get_input_image_paths(self) -> List[str]:
        """获取输入图片路径列表（自动从配置或默认目录获取，有 OSS 时转为 URL）"""
        paths = self._config.get('inputs', {}).get('image_paths', '')
        resolved = self._resolve_paths(paths)
        if resolved:
            return [self.to_oss_url(p) for p in resolved]
        # 自动从默认目录获取所有图片文件
        return [self.to_oss_url(str(p)) for p in self.list_images()]

    def get_input_video_paths(self) -> List[str]:
        """获取输入视频路径列表（自动从配置或默认目录获取，有 OSS 时转为 URL）"""
        paths = self._config.get('inputs', {}).get('video_paths', '')
        resolved = self._resolve_paths(paths)
        if resolved:
            return [self.to_oss_url(p) for p in resolved]
        # 自动从默认目录获取所有视频文件
        return [self.to_oss_url(str(p)) for p in self.list_videos()]

    def get_input_audio_paths(self) -> List[str]:
        """获取输入音频路径列表（自动从配置或默认目录获取，有 OSS 时转为 URL）"""
        paths = self._config.get('inputs', {}).get('audio_paths', '')
        resolved = self._resolve_paths(paths)
        if resolved:
            return [self.to_oss_url(p) for p in resolved]
        # 自动从默认目录获取所有音频文件
        return [self.to_oss_url(str(p)) for p in self.list_audios()]

    def get_base_url(self) -> str:
        """获取输入基础 URL

        优先级：
            1. 上层配置中的 base_input_url
            2. 项目内配置中的 oss.base_url
        """
        # 1. 上层配置
        parent_url = self._parent_config.get('base_input_url', '').strip()
        if parent_url:
            return parent_url

        # 2. 项目内配置
        return self._config.get('oss', {}).get('base_url', '').strip()

    def to_oss_url(self, local_path: str) -> str:
        """将本地路径转换为 OSS URL

        如果配置了 base_url，且路径是本地路径，则自动转换为 OSS URL。
        如果路径已经是 URL，直接返回。

        Args:
            local_path: 本地路径或 URL

        Returns:
            OSS URL 或原始 URL
        """
        if not local_path:
            return local_path

        # 如果已经是 URL，直接返回
        if local_path.startswith(('http://', 'https://')):
            return local_path

        base_url = self.get_base_url()
        if not base_url:
            return local_path

        # 解析本地路径为绝对路径
        abs_path = Path(local_path).resolve()

        # 获取相对于上层目录的相对路径
        try:
            rel_path = abs_path.relative_to(self.parent_dir.resolve())
            # 拼接为 OSS URL
            oss_url = f"{base_url.rstrip('/')}/{str(rel_path).replace(chr(92), '/')}"
            return oss_url
        except ValueError:
            # 如果路径不在上层目录内，返回原始路径
            return local_path

    def get_output_base_url(self) -> str:
        """获取输出基础 URL

        优先级：
            1. 上层配置中的 base_output_url
            2. 项目内配置中的 oss.output_dir
            3. 使用 base_input_url + /outputs 作为默认值

        Returns:
            输出基础 URL 或空字符串
        """
        # 1. 上层配置
        parent_url = self._parent_config.get('base_output_url', '').strip()
        if parent_url:
            return parent_url

        # 2. 项目内配置
        project_url = self._config.get('oss', {}).get('output_dir', '').strip()
        if project_url:
            return project_url

        # 3. 默认使用 base_input_url + /outputs
        base_input = self.get_base_url()
        if base_input:
            return f"{base_input.rstrip('/')}/outputs"

        return ''

    def get_output_url(self, filename: str) -> str:
        """获取输出文件的 URL

        Args:
            filename: 输出文件名（如 seedance_xxx.mp4）

        Returns:
            输出文件 URL 或空字符串
        """
        base_url = self.get_output_base_url()
        if not base_url:
            return ''
        return f"{base_url.rstrip('/')}/{filename}"

    def get_audio_dir(self) -> Path:
        """获取输入音频目录（上层目录的 audios/ 或配置覆盖）"""
        dir_name = self._config.get('paths', {}).get('audio_dir', 'audios')
        return self.parent_dir / dir_name

    def list_audios(self) -> List[Path]:
        """列出输入音频目录中的所有音频文件"""
        audio_dir = self.get_audio_dir()
        if not audio_dir.exists():
            return []

        audio_extensions = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}
        return [
            f for f in audio_dir.iterdir()
            if f.is_file() and f.suffix.lower() in audio_extensions
        ]

    def get_image_dir(self) -> Path:
        """获取输入图片目录（上层目录的 images/ 或配置覆盖）"""
        dir_name = self._config.get('paths', {}).get('image_dir', 'images')
        return self.parent_dir / dir_name

    def get_video_dir(self) -> Path:
        """获取输入视频目录（上层目录的 videos/ 或配置覆盖）"""
        dir_name = self._config.get('paths', {}).get('video_dir', 'videos')
        return self.parent_dir / dir_name

    def get_output_dir(self) -> Path:
        """获取输出结果目录（上层目录的 outputs/ 或配置覆盖）"""
        dir_name = self._config.get('paths', {}).get('output_dir', 'outputs')
        output_dir = self.parent_dir / dir_name

        # 确保目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def get_output_path(self, filename: str) -> Path:
        """获取输出文件路径（在输出目录中）"""
        return self.get_output_dir() / filename

    def list_images(self) -> List[Path]:
        """列出输入图片目录中的所有图片文件"""
        image_dir = self.get_image_dir()
        if not image_dir.exists():
            return []

        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        return [
            f for f in image_dir.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ]

    def list_videos(self) -> List[Path]:
        """列出输入视频目录中的所有视频文件"""
        video_dir = self.get_video_dir()
        if not video_dir.exists():
            return []

        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
        return [
            f for f in video_dir.iterdir()
            if f.is_file() and f.suffix.lower() in video_extensions
        ]

    def get_generate_audio(self) -> bool:
        """获取是否生成音频"""
        return self._config.get('generation', {}).get('generate_audio', True)

    def get_ratio(self) -> str:
        """获取视频比例"""
        return self._config.get('generation', {}).get('ratio', '16:9')

    def get_duration(self) -> int:
        """获取视频时长"""
        return self._config.get('generation', {}).get('duration', 5)

    def get_watermark(self) -> bool:
        """获取是否添加水印"""
        return self._config.get('generation', {}).get('watermark', True)

    def get_full_config(self) -> Dict[str, Any]:
        """获取完整配置字典（用于调试）"""
        return copy.deepcopy(self._config)

    def get_config_path(self) -> str:
        """获取项目内配置文件路径"""
        return str(self.config_path)

    def get_parent_config_path(self) -> Optional[str]:
        """获取上层配置文件路径（如果存在）"""
        home_config = Path.home() / self.PARENT_CONFIG_NAME
        if home_config.exists():
            return str(home_config)

        parent_config = self.project_root.parent / self.PARENT_CONFIG_NAME
        if parent_config.exists():
            return str(parent_config)

        return None

    def get_parent_dir(self) -> str:
        """获取上层目录路径"""
        return str(self.parent_dir)

    def validate(self) -> list:
        """验证配置完整性

        只验证必填项（API Key、模型 ID、提示词）。
        图片、视频、音频为可选，如果未配置则前端显示为空。

        Returns:
            错误列表，如果为空则表示配置有效
        """
        errors = []

        if not self.get_api_key():
            errors.append(
                "API Key 未配置（请设置环境变量 ARK_API_KEY 或创建 ~/.ark.yaml 或 ../.ark.yaml）"
            )

        if not self.get_model_id():
            errors.append("模型 ID 未配置")

        if not self.get_prompt():
            errors.append("文本提示词（prompt）未配置")

        # 可选：检查 ratio 值是否合法
        valid_ratios = ['16:9', '9:16', '1:1', '4:3', '3:4']
        if self.get_ratio() not in valid_ratios:
            errors.append(
                f"视频比例 '{self.get_ratio()}' 不合法，可选值：{', '.join(valid_ratios)}"
            )

        return errors

    def print_config(self, mask_api_key: bool = True) -> None:
        """打印当前配置（用于调试）

        Args:
            mask_api_key: 是否隐藏 API Key 的中间部分
        """
        api_key = self.get_api_key()
        if mask_api_key and api_key:
            masked = f"{api_key[:3]}...{api_key[-3:]}" if len(api_key) > 6 else "***"
        else:
            masked = api_key or "未配置"

        parent_config_path = self.get_parent_config_path()

        print("当前配置：")
        print(f"  API Key        : {masked}")
        if parent_config_path:
            print(f"  API Key 来源   : {parent_config_path}")
        print(f"  模型 ID        : {self.get_model_id()}")
        print(f"  提示词         : {self.get_prompt()}")
        print(f"  输入图片       : {self.get_input_image_paths() or '(空)'}")
        print(f"  输入视频       : {self.get_input_video_paths() or '(空)'}")
        print(f"  输入音频       : {self.get_input_audio_paths() or '(空)'}")
        print(f"  OSS 基础 URL   : {self.get_base_url() or '(未配置)'}")
        print(f"  图片目录       : {self.get_image_dir()}")
        print(f"  视频目录       : {self.get_video_dir()}")
        print(f"  音频目录       : {self.get_audio_dir()}")
        print(f"  输出目录       : {self.get_output_dir()}")
        print(f"  生成音频       : {self.get_generate_audio()}")
        print(f"  视频比例       : {self.get_ratio()}")
        print(f"  视频时长       : {self.get_duration()} 秒")
        print(f"  水印           : {self.get_watermark()}")
        print(f"  上层目录       : {self.get_parent_dir()}")
        print(f"  配置文件路径   : {self.get_config_path()}")
