import os
from uuid import uuid4
from typing import Any, Dict, Optional

from src.config import load_config
from src.api_client import APIClient
from src.decomposer import decompose
from src.scheduler import schedule
from src.executor import execute_wave_parallel
from src.collector import generate_report, save_report
from src.monitor import LiveMonitor
from src.plan_validator import validate_plan
from src.costs import CostTracker
from src.manifest import (
    build_manifest,
    create_execution_state,
    load_or_create_manifest,
    manifest_context,
    save_manifest,
    update_execution_state,
)


class Orchestrator:
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: str = "config/default.yaml"):
        self.config = config or load_config(config_path)
        self.cost_tracker = CostTracker(self.config.get("pricing", {}))
        self.client = APIClient(self.config, self.cost_tracker)
        self.model_config = self.config.get("models", {})

    def run(
        self,
        problem: str,
        output_dir: str = "output",
        model_map: Optional[Dict[str, str]] = None,
        manifest_root: Optional[str] = None,
    ) -> str:
        model_map = model_map or {}
        decomposer_model = model_map.get("decomposer", self.model_config.get("decomposer", "openai:gpt-4o-mini"))
        executor_model = model_map.get("executor_default", self.model_config.get("executor_default", "openai:gpt-4o-mini"))
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
        tasks = decompose(
            problem,
            self.client,
            decomposer_model,
            repair_model,
            repository_context,
        )

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

        # Override model assignment
        for task in tasks:
            if task.assigned_model == "default":
                task.assigned_model = executor_model

        waves = schedule(tasks)

        task_dir = os.path.join(output_dir, "tasks")
        result_dir = os.path.join(output_dir, "results")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)

        monitor = LiveMonitor(waves)
        monitor.start()

        for wave in waves:
            for task in wave.tasks:
                monitor.update(task.id, "running")
            state_callback = None
            if repository_root and execution_state is not None:
                state_callback = lambda result: update_execution_state(
                    repository_root, execution_state, result
                )
            if manifest is None and state_callback is None:
                execute_wave_parallel(wave, task_dir)
            else:
                execute_wave_parallel(
                    wave,
                    task_dir,
                    manifest=manifest,
                    state_callback=state_callback,
                )
            for res in wave.task_results:
                monitor.update(res["task_id"], res["status"])

        monitor.stop(self.cost_tracker.summary())

        report = generate_report(waves)
        report_path = save_report(report, result_dir)

        if repository_root:
            save_manifest(repository_root, build_manifest(repository_root))

        return report
