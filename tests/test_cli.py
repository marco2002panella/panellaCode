from typer.testing import CliRunner
from src.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output


def test_cli_run_requires_problem():
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0