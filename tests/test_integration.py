from src.scheduler import schedule
from src.collector import generate_report
from src.models import Task


def _make_task(tid: str, deps: list = None) -> Task:
    return Task(
        id=tid,
        description=f"Description for {tid}",
        context={"project_root": "/app", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "FastAPI", "language": "Python 3.12", "style": "", "code_split": []},
        dependencies=deps or [],
        level=0,
        assigned_model="openai:gpt-4o-mini",
    )


def test_full_pipeline_schedule_and_collect():
    tasks = [
        _make_task("t1"),
        _make_task("t2"),
        _make_task("t3", ["t1"]),
        _make_task("t4", ["t1", "t2"]),
        _make_task("t5", ["t3", "t4"]),
    ]
    waves = schedule(tasks)
    assert len(waves) == 3

    for wave in waves:
        for task in wave.tasks:
            wave.task_results.append({
                "task_id": task.id,
                "status": "completed",
                "error": None,
            })

    report = generate_report(waves)
    assert "Wave 0" in report
    assert "Wave 1" in report
    assert "Wave 2" in report
    assert "Completed: 5" in report
    assert "Failed: 0" in report
