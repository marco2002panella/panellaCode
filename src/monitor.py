from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from src.models import Task, Wave


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


ICON = {
    "pending": "⏳",
    "running": "🔄",
    "completed": "✅",
    "failed": "❌",
}


class LiveMonitor:
    def __init__(self, waves: List[Wave]):
        self.waves = waves
        self.console = Console()
        self._task_status: Dict[str, str] = {}
        self._total = 0
        for wave in waves:
            for task in wave.tasks:
                self._task_status[task.id] = "pending"
                self._total += 1

    def start(self):
        self.console.print(Panel("⚡ Execution started", style="bold green"))
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=20),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
            transient=False,
        )
        self._progress.start()
        for wave in self.waves:
            for task in wave.tasks:
                self._progress.add_task(f"{task.id}", total=self._total)
        self._update_bar()

    def _update_bar(self):
        if not hasattr(self, "_progress"):
            return
        completed = sum(1 for s in self._task_status.values() if s == "completed")
        pct = (completed / self._total * 100) if self._total else 0
        task_ids = list(self._progress.task_ids)
        for i, tid in enumerate(task_ids):
            self._progress.update(tid, completed=completed, visible=(i == 0))

    def update(self, task_id: str, status: str):
        self._task_status[task_id] = status
        self._update_bar()

    def log_event(self, message: str):
        self.console.print(f"[dim]{message}[/dim]")

    def stop(self):
        self._progress.stop()
        table = Table(title="📊 Results")
        table.add_column("Task", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Description", style="white")
        table.add_column("Model", style="dim")
        for wave in self.waves:
            for task in wave.tasks:
                status = self._task_status.get(task.id, "pending")
                table.add_row(
                    task.id,
                    ICON.get(status, "?"),
                    task.description[:50],
                    task.assigned_model,
                )
        completed = sum(1 for s in self._task_status.values() if s == "completed")
        failed = sum(1 for s in self._task_status.values() if s == "failed")
        self.console.print(table)
        self.console.print(f"\n✅ {completed}/{self._total} completed, ❌ {failed} failed\n")