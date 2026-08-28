from src.models import Task, Wave


def test_task_creation():
    task = Task(
        id="task_001",
        description="Implement auth endpoint",
        context={
            "project_root": "/app",
            "output_file": "src/auth.py",
            "related_files": ["src/db.py"],
        },
        conventions={
            "framework": "FastAPI",
            "language": "Python 3.12",
            "style": "type-hinted",
            "code_split": ["separate handlers"],
        },
        dependencies=[],
        level=0,
        assigned_model="openai:gpt-4o-mini",
    )
    assert task.id == "task_001"
    assert task.level == 0
    assert task.output_file == "src/auth.py"


def test_wave_creation():
    tasks = [
        Task(
            id="t1",
            description="A",
            context={"project_root": "/x", "output_file": "a.py", "related_files": []},
            conventions={"framework": "", "language": "", "style": "", "code_split": []},
            dependencies=[],
            level=0,
            assigned_model="openai:gpt-4o-mini",
        )
    ]
    wave = Wave(level=0, tasks=tasks, status="pending")
    assert wave.level == 0
    assert wave.status == "pending"
    assert len(wave.tasks) == 1
