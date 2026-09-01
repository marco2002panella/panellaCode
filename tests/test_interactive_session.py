from unittest.mock import MagicMock, patch
from src.interactive_session import InteractiveSession


def test_interactive_session_init():
    orch = MagicMock()
    orch.run.return_value = "report"
    session = InteractiveSession(orch, "Test problem", "output")
    assert session.orchestrator == orch
    assert session.problem == "Test problem"


def test_interactive_session_assigns_default_models_before_scheduling():
    from src.models import Task
    orch = MagicMock()
    orch.model_config = {"executor_default": "opencode_zen:big-pickle"}
    orch.router = MagicMock()
    orch.router.next_for_role.return_value = "opencode_zen:big-pickle"
    orch._decompose_with_repair.return_value = []
    orch._schedule_tasks.return_value = []

    session = InteractiveSession(orch, "Problem", "output")

    with patch.object(session, "input_handler") as _ih:
        try:
            session.run()
        except Exception:
            pass

    orch._assign_default_models.assert_called()
