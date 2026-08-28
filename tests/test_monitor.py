from src.monitor import Monitor, MonitoredTask, TaskStatus
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
    monitor = Monitor(waves)
    assert len(monitor.waves) == 1


def test_monitor_update_task():
    waves = [Wave(level=0, tasks=[_make_task("t1")], status="pending")]
    monitor = Monitor(waves)
    monitor.update_task("t1", "running")
    assert monitor.waves[0].tasks[0].status == "running"


def test_monitor_update_unknown_task():
    waves = [Wave(level=0, tasks=[_make_task("t1")], status="pending")]
    monitor = Monitor(waves)
    monitor.update_task("nonexistent", "running")
    assert monitor.waves[0].tasks[0].status == "pending"


def test_monitor_get_task_status():
    waves = [Wave(level=0, tasks=[_make_task("t1")], status="pending")]
    monitor = Monitor(waves)
    assert monitor.get_task_status("t1") == "pending"
    monitor.update_task("t1", "running")
    assert monitor.get_task_status("t1") == "running"


def test_monitor_get_task_status_unknown():
    waves = [Wave(level=0, tasks=[_make_task("t1")], status="pending")]
    monitor = Monitor(waves)
    assert monitor.get_task_status("unknown") is None


def test_monitor_total_tasks():
    waves = [
        Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending"),
        Wave(level=1, tasks=[_make_task("t3")], status="pending"),
    ]
    monitor = Monitor(waves)
    assert monitor.total_tasks == 3


def test_monitor_completed_tasks():
    waves = [Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending")]
    monitor = Monitor(waves)
    assert monitor.completed_tasks == 0
    monitor.update_task("t1", "completed")
    assert monitor.completed_tasks == 1


def test_monitor_failed_tasks():
    waves = [Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending")]
    monitor = Monitor(waves)
    assert monitor.failed_tasks == 0
    monitor.update_task("t1", "failed")
    assert monitor.failed_tasks == 1


def test_monitor_render():
    waves = [Wave(level=0, tasks=[_make_task("t1")], status="pending")]
    monitor = Monitor(waves)
    rendered = monitor.render()
    assert "t1" in rendered
    assert "Task t1" in rendered
    assert "Progress:" in rendered


def test_monitor_render_with_progress():
    waves = [Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending")]
    monitor = Monitor(waves)
    monitor.update_task("t1", "completed")
    monitor.update_task("t2", "failed")
    rendered = monitor.render()
    assert "1/2 completed" in rendered
    assert "1 failed" in rendered


def test_monitored_task_is_task_subclass():
    mt = MonitoredTask(
        id="t1",
        description="Test",
        context={},
        conventions={},
        dependencies=[],
        level=0,
        assigned_model="default",
    )
    assert isinstance(mt, Task)
    assert mt.status == "pending"


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
    monitor = Monitor(waves)
    monitor.update_task("t2", "running")
    assert monitor.waves[1].tasks[0].status == "running"
    assert monitor.waves[0].tasks[0].status == "pending"
