from typer.testing import CliRunner
from src.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--manifest" in result.stdout
    assert "run" in result.output


def test_cli_run_requires_problem():
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
