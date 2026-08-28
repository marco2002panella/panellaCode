import os
from typing import Any, Dict, List, Optional

from src.config import load_config
from src.api_client import APIClient
from src.decomposer import decompose
from src.scheduler import schedule
from src.executor import execute_wave
from src.collector import generate_report, save_report
from src.models import Wave


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
    ) -> str:
        model_map = model_map or {}
        decomposer_model = model_map.get("decomposer", self.model_config.get("decomposer", "openai:gpt-4o-mini"))
        executor_model = model_map.get("executor_default", self.model_config.get("executor_default", "openai:gpt-4o-mini"))

        # Phase 1: Decompose
        print("[1/4] Decomposing problem...")
        tasks = decompose(problem, self.client, decomposer_model)
        print(f"      Found {len(tasks)} subtasks")

        # Override model assignment
        for task in tasks:
            if task.assigned_model == "default":
                task.assigned_model = executor_model

        # Phase 2: Schedule
        print("[2/4] Scheduling tasks...")
        waves = schedule(tasks)
        for w in waves:
            print(f"      Wave {w.level}: {len(w.tasks)} tasks (parallel)")

        # Phase 3: Execute
        print("[3/4] Executing waves...")
        task_dir = os.path.join(output_dir, "tasks")
        result_dir = os.path.join(output_dir, "results")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)

        for wave in waves:
            print(f"\n  >>> Wave {wave.level} ({wave.status})")
            execute_wave(wave, task_dir)

        # Phase 4: Collect
        print("\n[4/4] Collecting results...")
        report = generate_report(waves)
        report_path = save_report(report, result_dir)
        print(f"      Report saved to {report_path}")

        return report