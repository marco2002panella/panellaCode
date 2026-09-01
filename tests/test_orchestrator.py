from unittest.mock import MagicMock, patch
import pytest

from src.orchestrator import Orchestrator
from src.models import Task, Wave


def _make_task(tid: str, deps: list = None, model: str = "default") -> Task:
    return Task(
        id=tid,
        description=f"Task {tid}",
        context={"project_root": "/x", "output_file": f"{tid}.out", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=deps or [],
        level=0,
        assigned_model=model,
    )


def test_orchestrator_init():
    orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
    assert orch is not None
    assert orch.client is not None


def test_orchestrator_init_with_config_path():
    with patch("src.orchestrator.load_config") as mock_load:
        mock_load.return_value = {"providers": {}, "models": {}}
        orch = Orchestrator(config_path="config/default.yaml")
        mock_load.assert_called_once_with("config/default.yaml")


def test_orchestrator_run_full_flow(tmp_path):
    tasks = [
        _make_task("t1"),
        _make_task("t2", ["t1"]),
    ]
    waves = [
        Wave(level=0, tasks=[tasks[0]], status="pending"),
        Wave(level=1, tasks=[tasks[1]], status="pending"),
    ]

    def mock_execute_v2_side_effect(w, d, m, c, r=None):
        w.task_results = [{"task_id": t.id, "status": "completed"} for t in w.tasks]
        return w

    with patch("src.orchestrator.decompose") as mock_decompose, \
         patch("src.orchestrator.schedule") as mock_schedule, \
         patch("src.orchestrator.execute_wave_v2") as mock_execute, \
         patch("src.orchestrator.generate_report") as mock_report, \
         patch("src.orchestrator.save_report") as mock_save, \
         patch("src.orchestrator.validate_plan") as mock_validate:

        mock_decompose.return_value = tasks
        mock_schedule.return_value = waves
        mock_execute.side_effect = mock_execute_v2_side_effect
        mock_validate.return_value = {"valid": True, "issues": [], "missing_tasks": []}
        mock_report.return_value = "# Report"
        mock_save.return_value = str(tmp_path / "report.md")

        orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
        result = orch.run("test problem", output_dir=str(tmp_path))

        mock_decompose.assert_called_once()
        mock_schedule.assert_called_once()
        assert mock_execute.call_count == 2
        mock_report.assert_called_once()
        mock_save.assert_called_once()
        assert result == "# Report"


def test_orchestrator_run_with_model_map(tmp_path):
    tasks = [
        _make_task("t1"),
    ]
    waves = [
        Wave(level=0, tasks=tasks, status="pending"),
    ]

    def mock_execute_side_effect(w, d):
        w.task_results = [{"task_id": t.id, "status": "completed"} for t in w.tasks]
        return w

    with patch("src.orchestrator.decompose") as mock_decompose, \
         patch("src.orchestrator.schedule") as mock_schedule, \
         patch("src.orchestrator.execute_wave_parallel") as mock_execute, \
         patch("src.orchestrator.generate_report") as mock_report, \
         patch("src.orchestrator.save_report") as mock_save:

        mock_decompose.return_value = tasks
        mock_schedule.return_value = waves
        mock_execute.side_effect = mock_execute_side_effect
        mock_report.return_value = "# Report"
        mock_save.return_value = str(tmp_path / "report.md")

        orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
        model_map = {
            "decomposer": "openai:gpt-4o",
            "executor_default": "openrouter:meta-llama/llama-3-8b-instruct",
        }
        orch.run("test problem", output_dir=str(tmp_path), model_map=model_map)

        # Verify decomposer model from model_map was used
        call_args = mock_decompose.call_args
        assert call_args[0][2] == "openai:gpt-4o"

        # Verify executor model override was applied
        assert tasks[0].assigned_model == "openrouter:meta-llama/llama-3-8b-instruct"


def test_orchestrator_run_creates_output_dirs(tmp_path):
    tasks = [_make_task("t1")]
    waves = [Wave(level=0, tasks=tasks, status="pending")]

    def mock_execute_side_effect(w, d):
        w.task_results = [{"task_id": t.id, "status": "completed"} for t in w.tasks]
        return w

    with patch("src.orchestrator.decompose") as mock_decompose, \
         patch("src.orchestrator.schedule") as mock_schedule, \
         patch("src.orchestrator.execute_wave_parallel") as mock_execute, \
         patch("src.orchestrator.generate_report") as mock_report, \
         patch("src.orchestrator.save_report") as mock_save:

        mock_decompose.return_value = tasks
        mock_schedule.return_value = waves
        mock_execute.side_effect = mock_execute_side_effect
        mock_report.return_value = "# Report"
        mock_save.return_value = str(tmp_path / "results" / "report.md")

        orch = Orchestrator(config={"providers": {}, "models": {}})
        out_dir = str(tmp_path / "output")
        orch.run("test problem", output_dir=out_dir)

        assert (tmp_path / "output" / "tasks").is_dir()
        assert (tmp_path / "output" / "results").is_dir()


def test_orchestrator_stops_before_scheduling_invalid_plan(tmp_path):
    tasks = [_make_task("t1")]
    with patch("src.orchestrator.decompose", return_value=tasks), \
         patch("src.orchestrator.validate_plan_v2", return_value={"valid": False, "issues": ["missing main"], "missing_tasks": []}), \
         patch("src.orchestrator.schedule") as mock_schedule:
        orch = Orchestrator(config={"providers": {}, "models": {}})
        with pytest.raises(RuntimeError, match="missing main"):
            orch.run("test problem", output_dir=str(tmp_path), manifest_root=str(tmp_path))
        mock_schedule.assert_not_called()


def test_assign_default_models_sets_executor_model():
    from src.models import Task
    from src.zen_router import ZenRouter
    orch = Orchestrator(config={
        "pricing": {}, "providers": {}, "models": {"executor_default": "opencode_zen:big-pickle"},
        "zen_free_models": ["opencode_zen:big-pickle"],
        "regolo_fallback_models": [],
    })
    tasks = [Task(id="t1", description="a", assigned_model="default")]
    orch._assign_default_models(tasks, "opencode_zen:big-pickle")
    assert tasks[0].assigned_model == "opencode_zen:big-pickle"
