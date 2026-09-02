# tests/test_run_tui_cli.py
"""Smoke-test that the GUI entrypoint (`run_gui`) wires a working
Orchestrator + TUIEventBridge and returns cleanly."""

from unittest.mock import MagicMock, patch


def test_run_gui_creates_orchestrator_and_runs_app():
    from src.tui.run_tui import run_gui

    mock_orch = MagicMock()
    mock_app = MagicMock()

    with patch("src.tui.run_tui.Orchestrator", return_value=mock_orch), \
         patch("src.tui.run_tui.AgentTUI", return_value=mock_app) as mock_tui_cls:
        run_gui(config="config/default.yaml")

    mock_tui_cls.assert_called_once()
    mock_app.run.assert_called_once()