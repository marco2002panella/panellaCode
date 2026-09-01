import tempfile
import shutil
from src.checkpointing import Checkpointer
from src.models import Task, Wave


def test_checkpointing_save_and_load_state():
    tmpdir = tempfile.mkdtemp()
    try:
        ckpt = Checkpointer(tmpdir)
        wave = Wave(level=0, tasks=[Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")], status="pending")
        ckpt.save_state([wave])

        loaded = ckpt.load_state()
        assert loaded["waves"][0]["level"] == 0
        assert loaded["waves"][0]["tasks"][0]["id"] == "t1"

        ckpt.cleanup()
    finally:
        shutil.rmtree(tmpdir)


def test_checkpointing_save_wave_state():
    tmpdir = tempfile.mkdtemp()
    try:
        ckpt = Checkpointer(tmpdir)
        wave = Wave(level=0, tasks=[Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")], status="completed")
        wave.task_results = [{"task_id": "t1", "status": "completed", "error": None}]
        ckpt.save_wave_state(wave)

        loaded = ckpt.load_state()
        assert loaded["waves"][0]["tasks"][0]["status"] == "completed"
    finally:
        shutil.rmtree(tmpdir)