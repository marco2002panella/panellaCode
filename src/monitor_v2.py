from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from src.models import Wave


class LiveMonitorV2:
    def __init__(self, waves: List[Wave], verbose: bool = False):
        self.waves = waves
        self.verbose = verbose
        self.console = Console()
        self._task_status: Dict[str, str] = {}
        self._total = 0
        for wave in waves:
            for task in wave.tasks:
                self._task_status[task.id] = "pending"
                self._total += 1
        self._progress: Optional[Progress] = None
        self._wave_progress: Optional[Progress] = None

    def start(self):
        self.console.print(Panel("⚡ Execution started", style="bold green"))
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
            transient=False,
        )
        self._progress.start()
        for wave in self.waves:
            for task in wave.tasks:
                self._progress.add_task(f"{task.id}", total=self._total)

    def start_validation(self):
        self.console.print(Panel("⏳ Validating plan...", style="bold yellow"))

    def end_validation(self, valid: bool):
        if valid:
            self.console.print(Panel("✅ Validation passed", style="bold green"))
        else:
            self.console.print(Panel("❌ Validation failed", style="bold red"))

    def start_wave(self, wave: Wave):
        self.console.print(Panel(f"🔄 Wave {wave.level} starting ({len(wave.tasks)} tasks)", style="bold cyan"))
        self._wave_progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=20),
            console=self.console,
            transient=False,
        )
        self._wave_progress.start()
        for task in wave.tasks:
            self._wave_progress.add_task(f"  {task.id}", total=len(wave.tasks))

    def update(self, task_id: str, status: str):
        self._task_status[task_id] = status
        if self._progress:
            completed = sum(1 for s in self._task_status.values() if s == "completed")
            for tid in self._progress.task_ids:
                self._progress.update(tid, completed=completed, visible=(tid == self._progress.task_ids[0]))

    def stop(self, cost_summary=None):
        if self._progress:
            self._progress.stop()
        if self._wave_progress:
            self._wave_progress.stop()
        table = self._build_table()
        self.console.print(table)
        completed = sum(1 for s in self._task_status.values() if s == "completed")
        failed = sum(1 for s in self._task_status.values() if s == "failed")
        self.console.print(f"\n✅ {completed}/{self._total} completed, ❌ {failed} failed\n")
        if cost_summary:
            cost = cost_summary.get("estimated_cost")
            cost_display = f"${cost:.6f}" if cost is not None else "unknown"
            self.console.print(
                f"Cost: {cost_display} | Calls: {cost_summary.get('calls', '?')} | "
                f"Tokens: {cost_summary.get('input_tokens', '?')} in / {cost_summary.get('output_tokens', '?')} out"
            )

    def _build_table(self):
        from rich.table import Table
        table = Table(title="📊 Results")
        table.add_column("Task", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Description", style="white")
        table.add_column("Model", style="dim")
        for wave in self.waves:
            for task in wave.tasks:
                status = self._task_status.get(task.id, "pending")
                icon = {"pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌"}.get(status, "?")
                table.add_row(task.id, icon, task.description[:50], task.assigned_model)
        return table