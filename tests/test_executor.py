import os
import shutil
import subprocess
import tempfile
import yaml
from unittest.mock import MagicMock, patch

from src.executor import build_opencode_prompt, execute_task, execute_wave, write_task_file
from src.models import Task, Wave


class TestWriteTaskFile:

    def test_write_task_file_creates_yaml(self):
        task = Task(
            id="task_001",
            description="Test task",
            context={"project_root": "/app", "output_file": "out.py", "related_files": []},
            conventions={"framework": "", "language": "Python", "style": "", "code_split": []},
            dependencies=[],
            level=0,
            assigned_model="openai:gpt-4o-mini",
        )
        output_dir = "/tmp/test_executor"
        path = write_task_file(task, output_dir)
        assert os.path.exists(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["id"] == "task_001"
        assert data["description"] == "Test task"
        assert data["context"]["project_root"] == "/app"
        assert data["assigned_model"] == "openai:gpt-4o-mini"
        shutil.rmtree(output_dir, ignore_errors=True)

    def test_write_task_file_creates_output_dir(self):
        task = Task(id="t1", description="d")
        nested = "/tmp/test_executor/nested/dir"
        path = write_task_file(task, nested)
        assert path.startswith(nested)
        assert os.path.exists(path)
        shutil.rmtree("/tmp/test_executor", ignore_errors=True)


class TestBuildOpencodePrompt:

    def test_prompt_contains_task_info(self):
        task = Task(
            id="t1",
            description="Build a parser",
            context={"project_root": "/app", "output_file": "parser.py", "related_files": ["a.py"]},
            conventions={"framework": "fastapi", "language": "Python", "style": "snake_case", "code_split": []},
        )
        prompt = build_opencode_prompt(task)
        assert "t1" in prompt
        assert "Build a parser" in prompt
        assert "/app" in prompt
        assert "parser.py" in prompt
        assert "fastapi" in prompt

    def test_prompt_handles_missing_context(self):
        task = Task(id="t2", description="x")
        prompt = build_opencode_prompt(task)
        assert "N/A" in prompt


class TestExecuteTask:

    @patch("src.executor.subprocess.run")
    def test_execute_task_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        task = Task(id="t1", description="d", assigned_model="openai:gpt-4o-mini")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_task(task, tmpdir)
        assert result["status"] == "completed"
        assert result["task_id"] == "t1"
        assert result["error"] is None
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "opencode" in call_args
        assert "openai:gpt-4o-mini" in call_args

    @patch("src.executor.subprocess.run")
    def test_execute_task_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="bad error")
        task = Task(id="t2", description="d")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_task(task, tmpdir)
        assert result["status"] == "failed"
        assert "bad error" in result["error"]

    @patch("src.executor.subprocess.run")
    def test_execute_task_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("opencode", 300)
        task = Task(id="t3", description="d")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_task(task, tmpdir)
        assert result["status"] == "failed"
        assert "timed out" in result["error"].lower()

    @patch("src.executor.subprocess.run")
    def test_execute_task_opencode_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        task = Task(id="t4", description="d")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_task(task, tmpdir)
        assert result["status"] == "failed"
        assert "not found" in result["error"].lower()


class TestExecuteWave:

    @patch("src.executor.execute_task")
    def test_execute_wave_all_success(self, mock_execute):
        mock_execute.return_value = {"task_id": "t1", "status": "completed", "error": None}
        tasks = [Task(id="t1", description="d", assigned_model="openai:gpt-4o-mini")]
        wave = Wave(level=0, tasks=tasks)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_wave(wave, tmpdir)
        assert result.status == "completed"
        assert len(result.task_results) == 1

    @patch("src.executor.execute_task")
    def test_execute_wave_partial_failure(self, mock_execute):
        mock_execute.return_value = {"task_id": "t1", "status": "failed", "error": "boom"}
        tasks = [Task(id="t1", description="d")]
        wave = Wave(level=0, tasks=tasks)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_wave(wave, tmpdir)
        assert result.status == "failed"

    def test_execute_wave_empty(self):
        wave = Wave(level=0, tasks=[])
        with tempfile.TemporaryDirectory() as tmpdir:
            result = execute_wave(wave, tmpdir)
        assert result.status == "completed"
        assert result.task_results == []
