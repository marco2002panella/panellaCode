from typer.testing import CliRunner
from src.cli import app


runner = CliRunner()


def test_cli_run_dry_run_flag_exists():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--dry-run" in result.output
    assert "-n" in result.output


def test_cli_run_resume_flag_exists():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--resume" in result.output
    assert "-r" in result.output


def test_cli_run_verbose_flag_exists():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--verbose" in result.output
    assert "-v" in result.output