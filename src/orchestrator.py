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
        self.client = APIClient(self.config)
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
        manifest = None
        execution_state = None
        repository_root = os.path.abspath(manifest_root) if manifest_root else None
        if repository_root:
            manifest = load_or_create_manifest(repository_root)
            execution_state = create_execution_state(
                repository_root, problem, uuid4().hex
            )

        # Phase 1: Decompose
        print("[1/4] Decomposing problem...")
        repository_context = manifest_context(manifest) if manifest else None
        tasks = decompose(
            problem,
            self.client,
            decomposer_model,
            repair_model,
            repository_context,
        )

        # Override model assignment
        for task in tasks:
            if task.assigned_model == "default":
                task.assigned_model = executor_model

        # Phase 2: Schedule
        print("[2/4] Scheduling tasks...")
        waves = schedule(tasks)

        # Phase 3: Execute
        print("[3/4] Executing waves...")
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

        monitor.stop()

        # Phase 4: Collect
        print("\n[4/4] Collecting results...")
        report = generate_report(waves)
        report_path = save_report(report, result_dir)
        print(f"      Report saved to {report_path}")

        if repository_root:
            save_manifest(repository_root, build_manifest(repository_root))

        return report
