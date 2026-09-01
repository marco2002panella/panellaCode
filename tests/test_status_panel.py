from src.status_panel import StatusPanel
from src.models import Wave, Task
from src.costs import CostTracker


def test_status_panel_init():
    wave = Wave(level=0, tasks=[Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")], status="pending")
    cost_tracker = CostTracker()
    panel = StatusPanel([wave], cost_tracker)
    assert len(panel.waves) == 1
    assert panel.cost_tracker == cost_tracker


def test_status_panel_get_status():
    wave = Wave(level=0, tasks=[Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")], status="pending")
    cost_tracker = CostTracker()
    panel = StatusPanel([wave], cost_tracker)
    panel.update("t1", "completed")
    status = panel.get_status()
    assert status["completed"] == 1
    assert status["pending"] == 0
