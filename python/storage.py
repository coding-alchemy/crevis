import json
from pathlib import Path
from typing import Optional, List
from models import Task, InputItem


class Storage:
    """任务信息持久化（JSONL）"""

    def __init__(self, storage_path: Path):
        """初始化存储

        Args:
            storage_path: task_history.jsonl 所在目录
        """
        self.storage_dir = Path(storage_path)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.storage_dir / "task_history.jsonl"

    def save_task(self, task: Task) -> None:
        """保存任务信息（追加到 JSONL）"""
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            json.dump(task.to_dict(), f, ensure_ascii=False)
            f.write("\n")

    def get_task(self, task_id: str) -> Optional[Task]:
        """根据 task_id 查询任务"""
        if not self.jsonl_path.exists():
            return None

        for task in self._read_all():
            if task.task_id == task_id:
                return task
        return None

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """查询任务列表，可按状态过滤"""
        if not self.jsonl_path.exists():
            return []

        tasks = self._read_all()
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def update_task_status(self, task_id: str, status: str, error_message: Optional[str] = None) -> None:
        """更新任务状态（重写整个文件）"""
        if not self.jsonl_path.exists():
            return

        tasks = self._read_all()
        updated = False
        for task in tasks:
            if task.task_id == task_id:
                task.status = status
                if error_message is not None:
                    task.error_message = error_message
                updated = True
                break

        if updated:
            self._write_all(tasks)

    def _read_all(self) -> List[Task]:
        """读取所有任务（去重，保留最新）"""
        tasks = {}
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    task = Task.from_dict(json.loads(line))
                    # 去重：同一 task_id 保留最新记录
                    tasks[task.task_id] = task
                except (json.JSONDecodeError, KeyError):
                    continue
        return list(tasks.values())

    def _write_all(self, tasks: List[Task]) -> None:
        """写入所有任务（覆盖文件）"""
        with open(self.jsonl_path, "w", encoding="utf-8") as f:
            for task in tasks:
                json.dump(task.to_dict(), f, ensure_ascii=False)
                f.write("\n")
