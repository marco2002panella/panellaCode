import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from src.models import Wave


class Checkpointer:
    CHECKPOINT_FILE = "checkpoint.yaml"

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.checkpoint_path = self.output_dir / self.CHECKPOINT_FILE
        self.run_id = str(uuid.uuid4())[:8]

    def save_state(self, waves: List[Wave]) -> None:
        state = {
            "version": 1,
            "run_id": self.run_id,
            "waves": [],
            "current_wave": 0,
            "timestamp": None,
        }
        for wave in waves:
            wave_data = {
                "level": wave.level,
                "status": wave.status,
                "tasks": [],
            }
            for task in wave.tasks:
                task_data = {"id": task.id, "status": "pending"}
                if wave.task_results:
                    result = next((r for r in wave.task_results if r["task_id"] == task.id), None)
                    if result:
                        task_data["status"] = result.get("status", "pending")
                        if result.get("error"):
                            task_data["error"] = result["error"]
                wave_data["tasks"].append(task_data)
            state["waves"].append(wave_data)
        state["timestamp"] = self._now_iso()
        self._write_yaml(state)

    def save_wave_state(self, wave: Wave) -> None:
        state = self._read_yaml()
        if state is None:
            state = {
                "version": 1,
                "run_id": self.run_id,
                "waves": [],
                "current_wave": 0,
                "timestamp": None,
            }
        wave_idx = wave.level
        while len(state["waves"]) <= wave_idx:
            state["waves"].append({"level": len(state["waves"]), "status": "pending", "tasks": []})
        state["waves"][wave_idx]["status"] = wave.status
        state["waves"][wave_idx]["tasks"] = []
        for task in wave.tasks:
            task_data = {"id": task.id}
            result = next((r for r in wave.task_results if r["task_id"] == task.id), None)
            if result:
                task_data["status"] = result.get("status", "pending")
                if result.get("error"):
                    task_data["error"] = result["error"]
            state["waves"][wave_idx]["tasks"].append(task_data)
        state["current_wave"] = wave_idx + 1
        state["timestamp"] = self._now_iso()
        self._write_yaml(state)

    def save_task_state(self, task_id: str, status: str, error: Optional[str] = None) -> None:
        state = self._read_yaml()
        if state is None:
            return
        for wave in state["waves"]:
            for task in wave["tasks"]:
                if task["id"] == task_id:
                    task["status"] = status
                    if error:
                        task["error"] = error
        state["timestamp"] = self._now_iso()
        self._write_yaml(state)

    def load_state(self) -> Optional[Dict[str, Any]]:
        return self._read_yaml()

    def cleanup(self) -> None:
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _write_yaml(self, data: Dict[str, Any]) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = __import__("tempfile").mkstemp(prefix=".checkpoint.", dir=self.output_dir)
        try:
            with __import__("os").fdopen(fd, "w") as f:
                yaml.safe_dump(data, f, sort_keys=False, allow_unicode=False)
            __import__("os").replace(tmp, self.checkpoint_path)
        except Exception:
            __import__("os").unlink(tmp)
            raise

    def _read_yaml(self) -> Optional[Dict[str, Any]]:
        if not self.checkpoint_path.exists():
            return None
        with self.checkpoint_path.open("r") as f:
            return yaml.safe_load(f)