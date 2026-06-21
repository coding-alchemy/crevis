from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import uuid

# 状态常量
PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
COMPLETED = "completed"
TIMEOUT = "timeout"


@dataclass
class InputItem:
    """输入素材项

    Attributes:
        id: 唯一标识
        type: 素材类型（image/video/audio）
        source: 来源（default/version）
        local_path: 本地文件路径
        remote_url: 远程 URL（远程化后填充）
    """
    id: str
    type: str  # image|video|audio
    source: str  # default|version
    local_path: str
    remote_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "InputItem":
        """从字典创建实例"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=data["type"],
            source=data["source"],
            local_path=data["local_path"],
            remote_url=data.get("remote_url"),
        )

    def to_dict(self) -> dict:
        """序列化为字典"""
        return asdict(self)


@dataclass
class Task:
    """任务信息

    Attributes:
        task_id: API 返回的远程任务标识
        version: 版本号（如 v20240621143000）
        model_id: 模型 ID
        input_list: 输入素材列表
        output_path: 输出目录路径
        request_params: 请求参数（脱敏后）
        status: 任务状态
        created_at: 创建时间
        completed_at: 完成时间
        error_message: 错误信息
    """
    task_id: str
    version: str
    model_id: str
    input_list: List[InputItem]
    output_path: str
    request_params: dict
    status: str = PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """从字典创建实例"""
        return cls(
            task_id=data["task_id"],
            version=data["version"],
            model_id=data["model_id"],
            input_list=[InputItem.from_dict(item) for item in data.get("input_list", [])],
            output_path=data["output_path"],
            request_params=data.get("request_params", {}),
            status=data.get("status", PENDING),
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
            error_message=data.get("error_message"),
        )

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "task_id": self.task_id,
            "version": self.version,
            "model_id": self.model_id,
            "input_list": [item.to_dict() for item in self.input_list],
            "output_path": self.output_path,
            "request_params": self.request_params,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }
