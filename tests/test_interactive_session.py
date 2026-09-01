from unittest.mock import MagicMock, patch
from src.interactive_session import InteractiveSession


def test_interactive_session_init():
    orch = MagicMock()
    orch.run.return_value = "report"
    session = InteractiveSession(orch, "Test problem", "output")
    assert session.orchestrator == orch
    assert session.problem == "Test problem"
