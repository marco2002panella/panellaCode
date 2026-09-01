import os
from uuid import uuid4
from typing import Any, Dict, Optional, List

from src.config import load_config
from src.api_client import APIClient
from src.decomposer import decompose
from src.scheduler import schedule
from src.executor import execute_wave_parallel
from src.executor_v2 import execute_wave_v2
from src.collector import generate_report, save_report
from src.monitor import LiveMonitor
from src.monitor_v2 import LiveMonitorV2
from src.plan_validator import validate_plan
from src.validator_v2 import validate_plan_v2
from src.costs import CostTracker
from src.manifest import (
    build_manifest,
    create_execution_state,
    load_or_create_manifest,
    manifest_context,
    save_manifest,
    update_execution_state,
)
from src.checkpointing import Checkpointer


class Orchestrator:
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: str = "config/default.yaml"):
        self.config = config or load_config(config_path)
        self.cost_tracker = CostTracker(self.config.get("pricing", {}))
        self.model_config = self.config.get("models", {})
        from src.zen_router import ZenRouter
        self.router = ZenRouter(
            zen_free_models=self.config.get("zen_free_models"),
            regolo_fallback_models=self.config.get("regolo_fallback_models"),
            executor_default=self.model_config.get("executor_default"),
        )
        self.client = APIClient(self.config, self.cost_tracker, router=self.router)

    def run(
        self,
        problem: str,
        output_dir: str = "output",
        model_map: Optional[Dict[str, str]] = None,
        manifest_root: Optional[str] = None,
        verbose: bool = False,
        dry_run: bool = False,
        resume: bool = False,
    ) -> str:
        model_map = model_map or {}
        decomposer_model = model_map.get("decomposer", self.model_config.get("decomposer", "opencode_zen:big-pickle"))
        executor_model = model_map.get("executor_default", self.model_config.get("executor_default", "opencode_zen:big-pickle"))
        repair_model = self.model_config.get("task_repair", executor_model)
        validator_model = self.model_config.get("plan_validator", executor_model)
        manifest = None
        execution_state = None
        repository_root = os.path.abspath(manifest_root) if manifest_root else None
        if repository_root:
            manifest = load_or_create_manifest(repository_root)
            execution_state = create_execution_state(
                repository_root, problem, uuid4().hex
            )

        repository_context = manifest_context(manifest) if manifest else None

        if dry_run:
            tasks = decompose(
                problem,
                self.client,
                decomposer_model,
                repair_model,
                repository_context,
            )
            if repository_root:
                validation = validate_plan_v2(
                    problem,
                    [task.model_dump() for task in tasks],
                    repository_context or "files: []",
                    validator_model,
                )
                self._print_validation(validation)
            self._print_tasks(tasks)
            return ""

        tasks = decompose(
            problem,
            self.client,
            decomposer_model,
            repair_model,
            repository_context,
        )

        if repository_root:
            validation = validate_plan_v2(
                problem,
                [task.model_dump() for task in tasks],
                repository_context or "files: []",
                validator_model,
            )
            if not validation["valid"]:
                issues = "; ".join(str(issue) for issue in validation["issues"])
                raise RuntimeError(f"Plan validation failed: {issues}")

        waves = schedule(tasks)

        if resume:
            checkpoint_dir = os.path.join(output_dir, "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)
            checkpointer = Checkpointer(checkpoint_dir)
            checkpoint_state = checkpointer.load_state()
            if checkpoint_state and checkpoint_state.get("waves"):
                for wave_idx, wave_data in enumerate(checkpoint_state["waves"]):
                    if wave_idx < len(waves):
                        waves[wave_idx].status = wave_data.get("status", "pending")
                        for task_data in wave_data.get("tasks", []):
                            task = next((t for t in waves[wave_idx].tasks if t.id == task_data["id"]), None)
                            if task:
                                task.status = task_data.get("status", "pending")

        self._assign_default_models(tasks, executor_model)

        if repository_root and not resume:
            monitor = LiveMonitorV2(waves, verbose=verbose)
            monitor.start_validation()
            validation = validate_plan_v2(
                problem,
                [task.model_dump() for task in tasks],
                repository_context or "files: []",
                validator_model,
            )
            monitor.end_validation(validation["valid"])
            if not validation["valid"]:
                issues = "; ".join(str(issue) for issue in validation["issues"])
                raise RuntimeError(f"Plan validation failed: {issues}")
        else:
            if repository_root:
                validation = validate_plan(
                    problem,
                    [task.model_dump() for task in tasks],
                    repository_context or "files: []",
                    validator_model,
                )
                if not validation["valid"]:
                    issues = "; ".join(str(issue) for issue in validation["issues"])
                    raise RuntimeError(f"Plan validation failed: {issues}")

        task_dir = os.path.join(output_dir, "tasks")
        result_dir = os.path.join(output_dir, "results")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)

        if resume:
            checkpoint_dir = os.path.join(output_dir, "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)
            checkpointer = Checkpointer(checkpoint_dir)
        else:
            checkpoint_dir = os.path.join(output_dir, "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)
            checkpointer = Checkpointer(checkpoint_dir)
            checkpointer.save_state(waves)

        monitor = LiveMonitorV2(waves, verbose=verbose)
        monitor.start()

        for wave in waves:
            monitor.start_wave(wave)
            state_callback = None
            if repository_root and execution_state is not None:
                state_callback = lambda result: update_execution_state(
                    repository_root, execution_state, result
                )
            execute_wave_v2(
                wave, task_dir, manifest,
                checkpointer if not resume else None,
                self.router,
            )
            for res in wave.task_results:
                monitor.update(res["task_id"], res["status"])

        monitor.stop(self.cost_tracker.summary())

        report = generate_report(waves)
        report_path = save_report(report, result_dir)

        if repository_root:
            save_manifest(repository_root, build_manifest(repository_root))

        if not resume:
            checkpointer.cleanup()

        return report

    def _print_tasks(self, tasks: List):
        console = __import__("rich").console.Console()
        console.print(f"Tasks ({len(tasks)}):")
        for task in tasks:
            console.print(f"  - {task.id}: {task.description[:60]}...")

    def _print_validation(self, validation: Dict):
        console = __import__("rich").console.Console()
        if validation["valid"]:
            console.print(console.render_str("[bold green]Plan validation passed[/bold green]"))
        else:
            console.print(console.render_str(f"[bold red]Plan validation failed:\n{validation['issues']}[/bold red]"))
    def _decompose_with_repair(self, problem: str, manifest_root: str = None):
        from src.decomposer import decompose
        from src.manifest import load_or_create_manifest, manifest_context
        
        decomposer_model = self.model_config.get("decomposer", "opencode_zen:big-pickle")
        repair_model = self.model_config.get("task_repair", self.model_config.get("executor_default", "opencode_zen:big-pickle"))
        
        repository_context = None
        if manifest_root:
            manifest = load_or_create_manifest(manifest_root)
            repository_context = manifest_context(manifest)
        
        return decompose(
            problem,
            self.client,
            decomposer_model,
            repair_model,
            repository_context,
        )

    def _assign_default_models(self, tasks, executor_model: str = None):
        executor_model = executor_model or self.router.next_for_role("executor_default")
        for task in tasks:
            if task.assigned_model == "default":
                task.assigned_model = executor_model

    def _schedule_tasks(self, tasks):
        from src.scheduler import schedule
        return schedule(tasks)

    def _execute_wave(self, wave, task_dir, manifest=None):
        from src.executor_v2 import execute_wave_v2
        from src.checkpointing import Checkpointer
        
        checkpoint_dir = f"{task_dir}/checkpoints"
        checkpointer = Checkpointer(checkpoint_dir)
        execute_wave_v2(wave, task_dir, manifest, checkpointer, self.router)

    def _generate_report(self, waves):
        from src.collector import generate_report
        return generate_report(waves)
