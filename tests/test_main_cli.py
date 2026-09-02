# tests/test_main_cli.py
"""Verify that `python3 main.py` (no subcommand) opens the GUI,
while existing subcommands and version branding stay unchanged."""

from unittest.mock import patch


def test_main_no_subcommand_opens_gui():
    from src.cli import _run_or_gui
    with patch("src.cli.run_gui") as mock_gui:
        _run_or_gui(config="config/default.yaml")
    mock_gui.assert_called_once_with(config="config/default.yaml")


def test_main_callback_no_subcommand_invokes_gui():
    from typer.testing import CliRunner
    from src.cli import app
    runner = CliRunner()
    with patch("src.cli.run_gui") as mock_gui:
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert mock_gui.call_count >= 1


def test_version_prints_problemSolver_branding(monkeypatch):
    from src.cli import version
    from typer.testing import CliRunner
    from src.cli import app
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "problemSolver" in result.output


def test_run_command_still_registered():
    from src.cli import app
    from typer.testing import CliRunner
    runner = CliRunner()
    # No subcommand => GUI path; run with explicit help must not crash.
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output