from typing import Dict, List, Optional
from src.models import Task, Wave


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MonitoredTask(Task):
    status: str = "pending"


class Monitor:
    def __init__(self, waves: List[Wave]):
        self.waves = waves
        self._task_map: Dict[str, MonitoredTask] = {}
        for wave in waves:
            original_tasks = wave.tasks
            wave.tasks = []
            for task in original_tasks:
                mt = MonitoredTask(**task.model_dump())
                self._task_map[task.id] = mt
                wave.tasks.append(mt)

    def update_task(self, task_id: str, status: str):
        if task_id in self._task_map:
            self._task_map[task_id].status = status

    def get_task_status(self, task_id: str) -> Optional[str]:
        return self._task_map.get(task_id).status if task_id in self._task_map else None

    @property
    def total_tasks(self) -> int:
        return len(self._task_map)

    @property
    def completed_tasks(self) -> int:
        return sum(1 for t in self._task_map.values() if t.status == "completed")

    @property
    def failed_tasks(self) -> int:
        return sum(1 for t in self._task_map.values() if t.status == "failed")

    def render(self) -> str:
        lines = []
        for wave in self.waves:
            wave_tasks = [self._task_map[t.id] for t in wave.tasks if t.id in self._task_map]
            status_icons = {
                "pending": "\u23f3\ufe0f",
                "running": "\U0001f504",
                "completed": "\u2705",
                "failed": "\u274c",
            }
            lines.append(f"\n[bold]Wave {wave.level}[/bold] [{wave.status}]:")
            for t in wave_tasks:
                icon = status_icons.get(t.status, "?")
                lines.append(f"  {icon} {t.id}: {t.description[:50]}")
        lines.append(f"\nProgress: {self.completed_tasks}/{self.total_tasks} completed, {self.failed_tasks} failed")
        return "\n".join(lines)