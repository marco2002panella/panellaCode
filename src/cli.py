import typer
from typing import Optional
from src.orchestrator import Orchestrator
from src.interactive_session import InteractiveSession
from src.tui.run_tui import run_gui

app = typer.Typer(name="problemSolver", help="Problem orchestrator with live TUI")


@app.callback(invoke_without_command=True)
def _main(ctx: typer.Context):
    """If invoked with no subcommand, launch the GUI."""
    if ctx.invoked_subcommand is None:
        run_gui(config="config/default.yaml")


def _run_or_gui(config: str = "config/default.yaml"):
    return run_gui(config=config)


@app.command()
def run(
    problem: str = typer.Argument(..., help="The problem to solve"),
    config: str = typer.Option("config/default.yaml", "--config", "-c", help="Config file path"),
    output: str = typer.Option("output", "--output", "-o", help="Output directory"),
    manifest: str = typer.Option(".", "--manifest", help="Project root for manifest files"),
    decomposer_model: Optional[str] = typer.Option(None, "--decomposer-model", help="Model for decomposition"),
    executor_model: Optional[str] = typer.Option(None, "--executor-model", help="Default model for execution"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show tasks without executing"),
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume from checkpoint"),
):

    model_map = {}
    if decomposer_model:
        model_map["decomposer"] = decomposer_model
    if executor_model:
        model_map["executor_default"] = executor_model

    orch = Orchestrator(config_path=config)
    report = orch.run(
        problem,
        output_dir=output,
        model_map=model_map if model_map else None,
        manifest_root=manifest,
        verbose=verbose,
        dry_run=dry_run,
        resume=resume,
    )
    typer.echo("\n" + report)


@app.command()
def interactive(
    problem: str = typer.Argument(..., help="The problem to solve"),
    config: str = typer.Option("config/default.yaml", "--config", "-c", help="Config file path"),
    output: str = typer.Option("output", "--output", "-o", help="Output directory"),
    manifest: str = typer.Option(".", "--manifest", help="Project root for manifest files"),
):
    """Run in interactive TUI mode with real-time monitoring and control."""
    orch = Orchestrator(config_path=config)
    session = InteractiveSession(orch, problem, output, manifest_root=manifest)
    
    try:
        report = session.run()
        typer.echo("\n" + report)
    except KeyboardInterrupt:
        typer.echo("\n⚠️  Session cancelled by user.")


@app.command()
def version():
    typer.echo("problemSolver 0.1.0")
