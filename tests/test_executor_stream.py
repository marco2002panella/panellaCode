# tests/test_executor_stream.py
import os
import subprocess
import sys
import tempfile
import shutil

from src.executor_stream import (
    _stream_subprocess_lines,
    execute_task_v2_stream,
    execute_wave_v2_stream,
    run_executor,
)
from src.models import Task, Wave
from src.checkpointing import Checkpointer


def test_stream_subprocess_lines_in_order():
    out = []
    err = []
    _stream_subprocess_lines(
        ["bash", "-c", "echo a; echo b; echo c >&2"],
        on_output=lambda line, is_stderr: (err if is_stderr else out).append(line),
        timeout=30,
    )
    assert out == ["a", "b"]
    assert err == ["c"]


def test_stream_subprocess_empty():
    _stream_subprocess_lines(["bash", "-c", "true"], on_output=lambda line, is_stderr: None, timeout=30)


def test_stream_subprocess_exit_code():
    rc = _stream_subprocess_lines(["bash", "-c", "exit 3"], on_output=lambda line, is_stderr: None, timeout=30)
    assert rc == 3


def test_stream_subprocess_not_found():
    rc = _stream_subprocess_lines(
        ["definitely-not-a-real-bin-xyz"],
        on_output=lambda line, is_stderr: None,
        timeout=5,
    )
    assert rc != 0


def test_execute_task_v2_stream_produces_result(monkeypatch):
    task = Task(id="t1", description="Test", context={"project_root": "/x", "output_file": "out.py"}, conventions={}, assigned_model="default")
    outdir = tempfile.mkdtemp()
    try:
        calls = []

        def fake_stream(cmd, on_output, timeout, **kw):
            on_output("fake line", False)
            return 0

        monkeypatch.setattr("src.executor_stream._stream_subprocess_lines", fake_stream)
        done = {}

        def on_done(result):
            done.update(result)

        monkeypatch.setattr("src.executor_stream.to_opencode_model", lambda m: m)
        res = execute_task_v2_stream(task, outdir, None, max_retries=1, on_output=None, on_done=on_done)
        assert res["status"] == "completed"
        assert res["task_id"] == "t1"
        result_path = os.path.join(outdir, "t1_result.md")
        with open(result_path) as f:
            assert f.read().strip() == "fake line"
    finally:
        shutil.rmtree(outdir)


def test_run_executor_blocking_delegates(monkeypatch):
    from src.executor_v2 import execute_task_v2

    task = Task(id="t1", description="Test", context={}, conventions={}, assigned_model="default")
    outdir = tempfile.mkdtemp()
    try:
        called = {"v": False}

        def fake_blocking(*a, **k):
            called["v"] = True
            return {"status": "completed", "task_id": "t1"}

        monkeypatch.setattr("src.executor_stream.execute_task_v2", fake_blocking)
        res = run_executor(task, outdir, mode="blocking")
        assert called["v"] is True
        assert res["status"] == "completed"
    finally:
        shutil.rmtree(outdir)


def test_run_executor_stream_default(monkeypatch):
    task = Task(id="t1", description="Test", context={}, conventions={}, assigned_model="default")
    outdir = tempfile.mkdtemp()
    try:
        called = {"v": False}

        def fake_streaming(*a, **k):
            called["v"] = True
            return {"status": "completed", "task_id": "t1"}

        # run_executor with mode="stream" calls execute_task_v2_stream
        monkeypatch.setattr("src.executor_stream.execute_task_v2_stream", fake_streaming)
        res = run_executor(task, outdir, mode="stream", on_output=lambda l, s: None)
        assert called["v"] is True
    finally:
        shutil.rmtree(outdir)


def test_execute_wave_v2_stream_preserves_wave():
    task1 = Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")
    task2 = Task(id="t2", description="B", context={}, conventions={}, assigned_model="default")
    wave = Wave(level=0, tasks=[task1, task2], status="pending")
    outdir = tempfile.mkdtemp()
    try:
        ckpt = Checkpointer(outdir)

        def fake_stream(cmd, on_output, timeout, **kw):
            on_output("line", False)
            return 0

        def fake_task(task, output_dir, manifest=None, max_retries=3, router=None,
                      on_output=None, on_done=None, proc_lock=None):
            result = {"task_id": task.id, "status": "completed", "result_path": os.path.join(output_dir, f"{task.id}_result.md")}
            if on_done:
                on_done(result)
            return result

        import src.executor_stream as es
        es._stream_subprocess_lines = fake_stream
        es.execute_task_v2_stream = fake_task

        result = execute_wave_v2_stream(wave, outdir, None, ckpt)
        assert result.status in ("completed", "failed")
        assert len(result.task_results) == 2
    finally:
        shutil.rmtree(outdir)