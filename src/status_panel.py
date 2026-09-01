from typing import Dict, List
from rich.console import Console
from rich.panel import Panel
from src.models import Wave
from src.costs import CostTracker


class StatusPanel:
    ICONS = {
        "pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌",
    }
    
    def __init__(self, waves: List[Wave], cost_tracker: CostTracker):
        self.waves = waves
        self.cost_tracker = cost_tracker
        self.console = Console()
        self._task_status: Dict[str, str] = {}
        self._total = 0
        for wave in waves:
            for task in wave.tasks:
                self._task_status[task.id] = "pending"
                self._total += 1
    
    def update(self, task_id: str, status: str) -> None:
        self._task_status[task_id] = status
    
    def get_status(self) -> Dict[str, int]:
        return {
            "completed": sum(1 for s in self._task_status.values() if s == "completed"),
            "failed": sum(1 for s in self._task_status.values() if s == "failed"),
            "running": sum(1 for s in self._task_status.values() if s == "running"),
            "pending": sum(1 for s in self._task_status.values() if s == "pending"),
        }
    
    def render(self) -> str:
        status = self.get_status()
        lines = [
            Panel(f"  ⏳ Pending: {status['pending']}\n"
                  f"  🔄 Running: {status['running']}\n"
                  f"  ✅ Completed: {status['completed']}\n"
                  f"  ❌ Failed: {status['failed']}", 
                  title="📊 Status", border_style="blue"),
        ]
        cost_summary = self.cost_tracker.summary()
        cost = cost_summary.get("estimated_cost")
        cost_display = f"${cost:.6f}" if cost is not None else "unknown"
        lines.append(Panel(f"  Calls: {cost_summary.get('calls', '?')}\n"
                          f"  Cost: {cost_display}", 
                          title="💰 Cost", border_style="green"))
        return "\n\n".join(str(p) for p in lines)
