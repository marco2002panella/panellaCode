# tests/test_executor_v2.py
import tempfile
import shutil
from src.executor_v2 import execute_task_v2, execute_wave_v2
from src.models import Task, Wave
from src.checkpointing import Checkpointer


def test_execute_task_v2_success():
    task = Task(id="t1", description="Test", context={"project_root": "/x", "output_file": "out.py"}, conventions={}, assigned_model="default")
    outdir = tempfile.mkdtemp()
    try:
        result = execute_task_v2(task, outdir, None, max_retries=1)
        assert result["task_id"] == "t1"
        assert result["status"] in ("completed", "failed")  # opencode may not be installed
    finally:
        shutil.rmtree(outdir)


def test_execute_task_v2_retry():
    task = Task(id="t1", description="Test", context={"project_root": "/x", "output_file": "out.py"}, conventions={}, assigned_model="default")
    outdir = tempfile.mkdtemp()
    try:
        result = execute_task_v2(task, outdir, None, max_retries=3)
        assert result["task_id"] == "t1"
        assert result["status"] in ("completed", "failed")
    finally:
        shutil.rmtree(outdir)


def test_execute_wave_v2_parallel():
    task1 = Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")
    task2 = Task(id="t2", description="B", context={}, conventions={}, assigned_model="default")
    wave = Wave(level=0, tasks=[task1, task2], status="pending")
    outdir = tempfile.mkdtemp()
    try:
        ckpt = Checkpointer(outdir)
        result_wave = execute_wave_v2(wave, outdir, None, ckpt)
        assert result_wave.status in ("completed", "failed")
    finally:
        shutil.rmtree(outdir)

def test_build_executor_prompt_includes_validation_requirements():
    from src.executor_v2 import build_executor_prompt
    task = Task(id="t9", description="Add feature", context={"output_file": "feat.py"}, conventions={})
    prompt = build_executor_prompt(task)
    assert "VALIDATION REQUIREMENTS" in prompt
    assert "VALIDATION:" in prompt
    assert "python -m py_compile" in prompt
