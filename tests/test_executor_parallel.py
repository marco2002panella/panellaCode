import shutil
import tempfile
import time
from unittest.mock import MagicMock, patch

from src.executor import execute_wave_parallel
from src.models import Task, Wave


def _make_task(tid: str) -> Task:
    return Task(
        id=tid,
        description=f"Task {tid}",
        context={"project_root": "/x", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=[],
        level=0,
        assigned_model="default",
    )


class TestExecuteWaveParallel:

    @patch("src.executor.execute_task")
    def test_parallel_executes_all_tasks(self, mock_execute):
        mock_execute.return_value = {"task_id": "t1", "status": "completed", "error": None}
        wave = Wave(level=0, tasks=[_make_task("t1"), _make_task("t2"), _make_task("t3")], status="pending")
        with tempfile.TemporaryDirectory() as tmpdir:
            result_wave = execute_wave_parallel(wave, tmpdir)
        assert result_wave.status == "completed"
        assert len(result_wave.task_results) == 3
        mock_execute.assert_called()

    @patch("src.executor.execute_task")
    def test_parallel_handles_partial_failure(self, mock_execute):
        def side_effect(task, output_dir):
            if task.id == "t2":
                return {"task_id": "t2", "status": "failed", "error": "boom"}
            return {"task_id": task.id, "status": "completed", "error": None}
        mock_execute.side_effect = side_effect
        wave = Wave(level=0, tasks=[_make_task("t1"), _make_task("t2"), _make_task("t3")], status="pending")
        with tempfile.TemporaryDirectory() as tmpdir:
            result_wave = execute_wave_parallel(wave, tmpdir)
        assert result_wave.status == "failed"
        completed = [r for r in result_wave.task_results if r["status"] == "completed"]
        failed = [r for r in result_wave.task_results if r["status"] == "failed"]
        assert len(completed) == 2
        assert len(failed) == 1

    @patch("src.executor.execute_task")
    def test_parallel_executes_tasks_concurrently(self, mock_execute):
        def slow_execute(task, output_dir):
            time.sleep(0.5)
            return {"task_id": task.id, "status": "completed", "error": None}
        mock_execute.side_effect = slow_execute
        wave = Wave(level=0, tasks=[_make_task("t1"), _make_task("t2"), _make_task("t3")], status="pending")
        start = time.time()
        with tempfile.TemporaryDirectory() as tmpdir:
            result_wave = execute_wave_parallel(wave, tmpdir)
        elapsed = time.time() - start
        assert elapsed < 1.5, f"Parallel execution should finish in under 1.5s, took {elapsed:.2f}s"
        assert result_wave.status == "completed"

    @patch("src.executor.execute_task")
    def test_parallel_handles_execute_task_exception(self, mock_execute):
        def side_effect(task, output_dir):
            if task.id == "t2":
                raise RuntimeError("unexpected error")
            return {"task_id": task.id, "status": "completed", "error": None}
        mock_execute.side_effect = side_effect
        wave = Wave(level=0, tasks=[_make_task("t1"), _make_task("t2"), _make_task("t3")], status="pending")
        with tempfile.TemporaryDirectory() as tmpdir:
            result_wave = execute_wave_parallel(wave, tmpdir)
        assert result_wave.status == "failed"
        failed_results = [r for r in result_wave.task_results if r["status"] == "failed"]
        assert len(failed_results) == 1
        assert "unexpected error" in failed_results[0]["error"]

    @patch("src.executor.execute_task")
    def test_parallel_empty_wave(self, mock_execute):
        wave = Wave(level=0, tasks=[], status="pending")
        with tempfile.TemporaryDirectory() as tmpdir:
            result_wave = execute_wave_parallel(wave, tmpdir)
        assert result_wave.status == "completed"
        assert result_wave.task_results == []