import pytest
from src.monitor import LiveMonitor, ICON, TaskStatus
from src.models import Task, Wave


def _make_task(tid: str, description: str = None) -> Task:
    return Task(
        id=tid,
        description=description or f"Task {tid}",
        context={"project_root": "/x", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=[],
        level=0,
        assigned_model="default",
    )


def test_monitor_init():
    waves = [Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending")]
    monitor = LiveMonitor(waves)
    assert len(monitor.waves) == 1
    assert monitor._total == 2


def test_monitor_update_task():
    waves = [Wave(level=0, tasks=[_make_task("t1")], status="pending")]
    monitor = LiveMonitor(waves)
    monitor.update("t1", "running")
    assert monitor._task_status["t1"] == "running"


def test_monitor_update_unknown_task():
    waves = [Wave(level=0, tasks=[_make_task("t1")], status="pending")]
    monitor = LiveMonitor(waves)
    monitor.update("nonexistent", "running")
    assert monitor._task_status["t1"] == "pending"


def test_monitor_total_tasks():
    waves = [
        Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending"),
        Wave(level=1, tasks=[_make_task("t3")], status="pending"),
    ]
    monitor = LiveMonitor(waves)
    assert monitor._total == 3


def test_monitor_count_completed():
    waves = [Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending")]
    monitor = LiveMonitor(waves)
    completed = sum(1 for s in monitor._task_status.values() if s == "completed")
    assert completed == 0
    monitor.update("t1", "completed")
    completed = sum(1 for s in monitor._task_status.values() if s == "completed")
    assert completed == 1


def test_monitor_count_failed():
    waves = [Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending")]
    monitor = LiveMonitor(waves)
    failed = sum(1 for s in monitor._task_status.values() if s == "failed")
    assert failed == 0
    monitor.update("t1", "failed")
    failed = sum(1 for s in monitor._task_status.values() if s == "failed")
    assert failed == 1


def test_icon_mapping():
    assert ICON["pending"] == "⏳"
    assert ICON["running"] == "🔄"
    assert ICON["completed"] == "✅"
    assert ICON["failed"] == "❌"


def test_task_status_constants():
    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.RUNNING == "running"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.FAILED == "failed"


def test_monitor_multiple_waves():
    waves = [
        Wave(level=0, tasks=[_make_task("t1")], status="pending"),
        Wave(level=1, tasks=[_make_task("t2")], status="pending"),
    ]
    monitor = LiveMonitor(waves)
    monitor.update("t2", "running")
    assert monitor._task_status["t2"] == "running"
    assert monitor._task_status["t1"] == "pending"