from unittest.mock import patch, MagicMock
import pytest
import tempfile
import shutil

from src.orchestrator import Orchestrator
from src.models import Task, Wave


def test_orchestrator_run_dry_run():
    orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
    tmpdir = tempfile.mkdtemp()
    try:
        with patch("src.orchestrator.decompose") as mock_decompose, \
             patch("src.orchestrator.validate_plan_v2") as mock_validate:
            mock_decompose.return_value = []
            mock_validate.return_value = {"valid": True, "issues": [], "missing_tasks": []}
            report = orch.run("Test problem", output_dir=tmpdir, dry_run=True)
            assert report == ""
    finally:
        shutil.rmtree(tmpdir)


def test_orchestrator_run_resume():
    orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
    tmpdir = tempfile.mkdtemp()
    try:
        with patch("src.orchestrator.decompose") as mock_decompose, \
             patch("src.checkpointing.Checkpointer") as mock_ckpt_class, \
             patch("src.orchestrator.validate_plan") as mock_validate, \
             patch("src.orchestrator.schedule") as mock_schedule, \
             patch("src.orchestrator.execute_wave_v2") as mock_execute, \
             patch("src.orchestrator.generate_report") as mock_report, \
             patch("src.orchestrator.save_report") as mock_save:
            mock_decompose.return_value = []
            mock_ckpt = MagicMock()
            mock_ckpt.load_state.return_value = None
            mock_ckpt_class.return_value = mock_ckpt
            mock_validate.return_value = {"valid": True, "issues": [], "missing_tasks": []}
            mock_schedule.return_value = []
            mock_report.return_value = "# Report"
            mock_save.return_value = str(tmpdir) + "/report.md"
            report = orch.run("Test problem", output_dir=tmpdir, resume=True)
            assert "completed" in report.lower() or "# Report" in report
    finally:
        shutil.rmtree(tmpdir)


def test_orchestrator_run_verbose():
    orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
    tmpdir = tempfile.mkdtemp()
    try:
        task = Task(
            id="t1",
            description="Test task",
            context={},
            conventions={},
            dependencies=[],
            level=0,
            assigned_model="default",
        )
        wave = Wave(level=0, tasks=[task], status="pending")
        
        with patch("src.orchestrator.decompose") as mock_decompose, \
             patch("src.orchestrator.validate_plan") as mock_validate, \
             patch("src.orchestrator.schedule") as mock_schedule, \
             patch("src.orchestrator.execute_wave_v2") as mock_execute, \
             patch("src.orchestrator.generate_report") as mock_report, \
             patch("src.orchestrator.save_report") as mock_save, \
             patch("src.orchestrator.LiveMonitorV2") as mock_monitor_class:
            mock_decompose.return_value = [task]
            mock_validate.return_value = {"valid": True, "issues": [], "missing_tasks": []}
            mock_schedule.return_value = [wave]
            mock_monitor = MagicMock()
            mock_monitor_class.return_value = mock_monitor
            mock_report.return_value = "# Report"
            mock_save.return_value = str(tmpdir) + "/report.md"
            report = orch.run("Test problem", output_dir=tmpdir, verbose=True)
            assert mock_monitor_class.call_count >= 1
            for call_obj in mock_monitor_class.call_args_list:
                call_kwargs = call_obj[1]
                assert call_kwargs.get("verbose") is True
    finally:
        shutil.rmtree(tmpdir)