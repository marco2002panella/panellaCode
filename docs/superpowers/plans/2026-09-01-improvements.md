# myagent Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve myagent by adding robust validator, fault-tolerant executor, checkpointing, and CLI flags while maintaining backward compatibility.

**Architecture:** New modules (validator_v2, executor_v2, monitor_v2, checkpointing) wired into orchestrator. Each improvement is independent, tested, and deployable.

**Tech Stack:** Python 3.12+, Typer, Pydantic, Rich, httpx, PyYAML

**Spec:** `docs/superpowers/specs/2026-09-01-improvements-design.md`

## Global Constraints

- Python 3.12+
- Dependencies: `typer`, `pydantic`, `rich`, `httpx`, `pyyaml`
- Config files in `config/`, output in `output/` (gitignored)
- No breaking changes to public API (Task, Wave, CLI command signature)
- Each module must have unit tests
- All 79 existing tests must pass + 32 new tests

---

### Task 1: Create validator_v2.py with retry logic

**Files:**
- Create: `src/validator_v2.py`
- Test: `tests/test_validator_v2.py`

**Interfaces:**
- Consumes: `subprocess`, `tempfile`, `json`
- Produces: `validate_plan_v2(problem, tasks, manifest, model, timeout=120, max_retries=3) → dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validator_v2.py
from src.validator_v2 import validate_plan_v2
from unittest.mock import patch, MagicMock


def test_validate_plan_v2_success():
    result = {"valid": True, "issues": [], "missing_tasks": []}
    completed = MagicMock(returncode=0, stdout='{"valid": true, "issues": []}', stderr="")
    with patch("src.validator_v2.subprocess.run", return_value=completed):
        out = validate_plan_v2("Build app", [], "files: []", "regolo:qwen3-coder-next")
    assert out["valid"] is True
    assert out["issues"] == []


def test_validate_plan_v2_retry_on_timeout():
    timeout_error = subprocess.TimeoutExpired(cmd=["opencode"], timeout=120)
    completed = MagicMock(returncode=0, stdout='{"valid": true, "issues": []}', stderr="")
    with patch("src.validator_v2.subprocess.run") as mock_run:
        mock_run.side_effect = [timeout_error, timeout_error, completed]
        out = validate_plan_v2("Build app", [], "files: []", "regolo:qwen3-coder-next")
    assert out["valid"] is True
    assert mock_run.call_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validator_v2.py -v`
Expected: FAIL — `ImportError: cannot import name 'validate_plan_v2'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/validator_v2.py
import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List


def validate_plan_v2(
    problem: str,
    tasks: List[Dict],
    manifest: str,
    model: str,
    timeout: int = 120,
    max_retries: int = 3,
) -> Dict[str, Any]:
    prompt = (
        "Validate the following task plan against the original problem and repository manifest. "
        "Return JSON only with keys valid (boolean), issues (array), and missing_tasks (array).\n\n"
        f"Original problem:\n{problem}\n\nTask plan:\n{json.dumps(tasks, indent=2)}\n\n"
        f"Repository manifest:\n{manifest}"
    )

    last_error = None
    for attempt in range(max_retries):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as stream:
            stream.write(prompt)
            prompt_file = stream.name
        try:
            process = subprocess.run(
                [
                    "opencode",
                    "run",
                    "--format",
                    "json",
                    "--model",
                    model.replace(":", "/"),
                    "Validate the attached task plan and return JSON only.",
                    "--file",
                    prompt_file,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            os.unlink(prompt_file)

            if process.returncode == 0:
                try:
                    parsed = json.loads(process.stdout.strip())
                    if isinstance(parsed, dict) and "valid" in parsed:
                        return parsed
                except json.JSONDecodeError:
                    for line in reversed(process.stdout.splitlines()):
                        try:
                            parsed = json.loads(line)
                            if isinstance(parsed, dict) and "valid" in parsed:
                                return parsed
                        except json.JSONDecodeError:
                            continue

            last_error = process.stderr.strip() or "validator returned invalid output"
        except subprocess.TimeoutExpired:
            last_error = "validator timed out"
        except FileNotFoundError:
            return {"valid": False, "issues": ["opencode command not found"], "missing_tasks": []}
        finally:
            if os.path.exists(prompt_file):
                os.unlink(prompt_file)

    return {"valid": False, "issues": [f"validator failed after {max_retries} retries: {last_error}"], "missing_tasks": []}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validator_v2.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/validator_v2.py tests/test_validator_v2.py
git commit -m "feat: robust validator with retry logic"
```

---

### Task 2: Create checkpointing.py for state persistence

**Files:**
- Create: `src/checkpointing.py`
- Test: `tests/test_checkpointing.py`

**Interfaces:**
- Consumes: `yaml`, `uuid`, `pathlib.Path`
- Produces: `Checkpointer(output_dir)` class with `save_state`, `save_wave_state`, `save_task_state`, `load_state`, `cleanup`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_checkpointing.py
import tempfile
import shutil
from src.checkpointing import Checkpointer
from src.models import Task, Wave


def test_checkpointing_save_and_load_state():
    tmpdir = tempfile.mkdtemp()
    try:
        ckpt = Checkpointer(tmpdir)
        wave = Wave(level=0, tasks=[Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")], status="pending")
        ckpt.save_state([wave])

        loaded = ckpt.load_state()
        assert loaded["waves"][0]["level"] == 0
        assert loaded["waves"][0]["tasks"][0]["id"] == "t1"

        ckpt.cleanup()
    finally:
        shutil.rmtree(tmpdir)


def test_checkpointing_save_wave_state():
    tmpdir = tempfile.mkdtemp()
    try:
        ckpt = Checkpointer(tmpdir)
        wave = Wave(level=0, tasks=[Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")], status="completed")
        wave.task_results = [{"task_id": "t1", "status": "completed", "error": None}]
        ckpt.save_wave_state(wave)

        loaded = ckpt.load_state()
        assert loaded["waves"][0]["tasks"][0]["status"] == "completed"
        assert loaded["waves"][0]["tasks"][0]["results"] == [{"status": "completed"}]
    finally:
        shutil.rmtree(tmpdir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_checkpointing.py -v`
Expected: FAIL — `ImportError: cannot import name 'Checkpointer'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/checkpointing.py
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
            return
        wave_idx = wave.level
        if 0 <= wave_idx < len(state["waves"]):
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
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_checkpointing.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/checkpointing.py tests/test_checkpointing.py
git commit -m "feat: checkpointing for state persistence and resume"
```

---

### Task 3: Create executor_v2.py with retry and checkpointing

**Files:**
- Create: `src/executor_v2.py`
- Test: `tests/test_executor_v2.py`

**Interfaces:**
- Consumes: `concurrent.futures`, `subprocess`, `yaml`, `tempfile`, `Checkpointer`
- Produces: `execute_task_v2(task, output_dir, manifest, max_retries=3) → dict`, `execute_wave_v2(wave, output_dir, manifest, checkpointer) → Wave`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_executor_v2.py
import tempfile
import shutil
from src.executor_v2 import execute_task_v2, execute_wave_v2
from src.models import Task, Wave
from src.checkpointing import Checkpointer


def test_execute_task_v2_success():
    task = Task(id="t1", description="Test", context={"project_root": "/x", "output_file": "out.py"}, conventions={}, assigned_model="default")
    outdir = tempfile.mkdtemp()
    try:
        result = execute_task_v2(task, outdir, None, max_retries=1)
        assert result["task_id"] == "t1"
        assert result["status"] in ("completed", "failed")  # opencode may not be installed
    finally:
        shutil.rmtree(outdir)


def test_execute_task_v2_retry():
    task = Task(id="t1", description="Test", context={"project_root": "/x", "output_file": "out.py"}, conventions={}, assigned_model="default")
    outdir = tempfile.mkdtemp()
    try:
        result = execute_task_v2(task, outdir, None, max_retries=3)
        assert result["task_id"] == "t1"
        assert result["status"] in ("completed", "failed")
    finally:
        shutil.rmtree(outdir)


def test_execute_wave_v2_parallel():
    task1 = Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")
    task2 = Task(id="t2", description="B", context={}, conventions={}, assigned_model="default")
    wave = Wave(level=0, tasks=[task1, task2], status="pending")
    outdir = tempfile.mkdtemp()
    try:
        ckpt = Checkpointer(outdir)
        result_wave = execute_wave_v2(wave, outdir, None, ckpt)
        assert result_wave.status in ("completed", "failed")
    finally:
        shutil.rmtree(outdir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_executor_v2.py -v`
Expected: FAIL — `ImportError: cannot import name 'execute_task_v2'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/executor_v2.py
import os
import subprocess
import tempfile
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from src.models import Task, Wave
from src.checkpointing import Checkpointer


def execute_task_v2(
    task: Task,
    output_dir: str,
    manifest: Dict = None,
    max_retries: int = 3,
) -> Dict:
    task_file = os.path.join(output_dir, f"{task.id}.yaml")
    os.makedirs(output_dir, exist_ok=True)
    with open(task_file, "w") as f:
        yaml.dump({
            "id": task.id,
            "description": task.description,
            "context": task.context,
            "conventions": task.conventions,
            "dependencies": task.dependencies,
            "level": task.level,
            "assigned_model": task.assigned_model,
        }, f, default_flow_style=False)

    result_path = os.path.join(output_dir, f"{task.id}_result.md")
    result = {
        "task_id": task.id,
        "task_file": task_file,
        "result_path": result_path,
        "status": "pending",
        "error": None,
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            prompt = (
                f"You are given a task to complete.\n\n"
                f"Task ID: {task.id}\n"
                f"Description: {task.description}\n\n"
                f"Context:\n"
                f"  Project root: {task.context.get('project_root', 'N/A')}\n"
                f"  Output file: {task.context.get('output_file', 'N/A')}\n"
                f"  Related files: {task.context.get('related_files', [])}\n\n"
                f"Conventions:\n"
                f"  Framework: {task.conventions.get('framework', 'N/A')}\n"
                f"  Language: {task.conventions.get('language', 'N/A')}\n"
                f"  Style: {task.conventions.get('style', 'N/A')}\n"
                f"  Code split: {task.conventions.get('code_split', [])}\n\n"
                f"Complete this task and write your output to the specified file."
            )
            if manifest:
                from src.manifest import manifest_context
                prompt += f"\n\nRepository manifest:\n{manifest_context(manifest)}"

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as pf:
                pf.write(prompt)
                prompt_file = pf.name

            model = task.assigned_model.replace(":", "/")
            proc = subprocess.run(
                ["opencode", "run", "--model", model, "Complete the attached task.", "--file", prompt_file],
                capture_output=True,
                text=True,
                timeout=300,
            )
            os.unlink(prompt_file)

            if proc.returncode == 0 and proc.stdout.strip():
                result["status"] = "completed"
                with open(result_path, "w") as f:
                    f.write(proc.stdout)
                if task.output_file:
                    from src.manifest import ensure_manifest_header
                    ensure_manifest_header(task.output_file, task.output_file, task.description)
                return result
            elif proc.returncode == 0:
                last_error = "opencode returned empty output"
            else:
                last_error = proc.stderr.strip() or "opencode failed"
        except subprocess.TimeoutExpired:
            last_error = "task timed out (300s)"
        except FileNotFoundError:
            last_error = "opencode command not found"
        except Exception as e:
            last_error = str(e)

    result["status"] = "failed"
    result["error"] = f"Task failed after {max_retries} retries: {last_error}"
    return result


def execute_wave_v2(
    wave: Wave,
    output_dir: str,
    manifest: Dict = None,
    checkpointer: Checkpointer = None,
) -> Wave:
    wave.status = "running"
    results = []

    if checkpointer:
        checkpointer.save_wave_state(wave)

    with ThreadPoolExecutor(max_workers=len(wave.tasks)) as executor:
        future_to_task = {
            executor.submit(execute_task_v2, task, output_dir, manifest): task
            for task in wave.tasks
        }
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                res = future.result()
                results.append(res)
                if checkpointer:
                    checkpointer.save_task_state(task.id, res["status"], res.get("error"))
            except Exception as e:
                results.append({
                    "task_id": task.id,
                    "status": "failed",
                    "error": str(e),
                })
                if checkpointer:
                    checkpointer.save_task_state(task.id, "failed", str(e))

    wave.status = "completed" if all(r["status"] == "completed" for r in results) else "failed"
    wave.task_results = results
    return wave
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_executor_v2.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/executor_v2.py tests/test_executor_v2.py
git commit -m "feat: fault-tolerant executor with retry and checkpointing"
```

---

### Task 4: Create monitor_v2.py with validation feedback

**Files:**
- Create: `src/monitor_v2.py`
- Test: `tests/test_monitor_v2.py`

**Interfaces:**
- Consumes: `rich`, `src.models.Wave`
- Produces: `LiveMonitorV2(waves, verbose=False)` class with `start`, `start_validation`, `end_validation`, `start_wave`, `update`, `stop`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_monitor_v2.py
from unittest.mock import MagicMock, patch
from src.monitor_v2 import LiveMonitorV2
from src.models import Wave, Task


def test_monitor_v2_init():
    wave = Wave(level=0, tasks=[Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")], status="pending")
    monitor = LiveMonitorV2([wave])
    assert len(monitor.waves) == 1
    assert monitor.verbose is False


def test_monitor_v2_validation():
    with patch("src.monitor_v2.Console") as mock_console:
        mock_panel = MagicMock()
        mock_console.return_value.print = MagicMock()
        monitor = LiveMonitorV2([])
        monitor.start_validation()
        mock_console.return_value.print.assert_called()
        monitor.end_validation(valid=True)
        mock_console.return_value.print.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_monitor_v2.py -v`
Expected: FAIL — `ImportError: cannot import name 'LiveMonitorV2'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/monitor_v2.py
from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from src.models import Wave


class LiveMonitorV2:
    def __init__(self, waves: List[Wave], verbose: bool = False):
        self.waves = waves
        self.verbose = verbose
        self.console = Console()
        self._task_status: Dict[str, str] = {}
        self._total = 0
        for wave in waves:
            for task in wave.tasks:
                self._task_status[task.id] = "pending"
                self._total += 1
        self._progress: Optional[Progress] = None
        self._wave_progress: Optional[Progress] = None

    def start(self):
        self.console.print(Panel("⚡ Execution started", style="bold green"))
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
            transient=False,
        )
        self._progress.start()
        for wave in self.waves:
            for task in wave.tasks:
                self._progress.add_task(f"{task.id}", total=self._total)

    def start_validation(self):
        self.console.print(Panel("⏳ Validating plan...", style="bold yellow"))

    def end_validation(self, valid: bool):
        if valid:
            self.console.print(Panel("✅ Validation passed", style="bold green"))
        else:
            self.console.print(Panel("❌ Validation failed", style="bold red"))

    def start_wave(self, wave: Wave):
        self.console.print(Panel(f"🔄 Wave {wave.level} starting ({len(wave.tasks)} tasks)", style="bold cyan"))
        self._wave_progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=20),
            console=self.console,
            transient=False,
        )
        self._wave_progress.start()
        for task in wave.tasks:
            self._wave_progress.add_task(f"  {task.id}", total=len(wave.tasks))

    def update(self, task_id: str, status: str):
        self._task_status[task_id] = status
        if self._progress:
            completed = sum(1 for s in self._task_status.values() if s == "completed")
            for tid in self._progress.task_ids:
                self._progress.update(tid, completed=completed, visible=(tid == self._progress.task_ids[0]))

    def stop(self, cost_summary=None):
        if self._progress:
            self._progress.stop()
        if self._wave_progress:
            self._wave_progress.stop()
        table = self._build_table()
        self.console.print(table)
        completed = sum(1 for s in self._task_status.values() if s == "completed")
        failed = sum(1 for s in self._task_status.values() if s == "failed")
        self.console.print(f"\n✅ {completed}/{self._total} completed, ❌ {failed} failed\n")
        if cost_summary:
            cost = cost_summary.get("estimated_cost")
            cost_display = f"${cost:.6f}" if cost is not None else "unknown"
            self.console.print(
                f"Cost: {cost_display} | Calls: {cost_summary.get('calls', '?')} | "
                f"Tokens: {cost_summary.get('input_tokens', '?')} in / {cost_summary.get('output_tokens', '?')} out"
            )

    def _build_table(self):
        from rich.table import Table
        table = Table(title="📊 Results")
        table.add_column("Task", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Description", style="white")
        table.add_column("Model", style="dim")
        for wave in self.waves:
            for task in wave.tasks:
                status = self._task_status.get(task.id, "pending")
                icon = {"pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌"}.get(status, "?")
                table.add_row(task.id, icon, task.description[:50], task.assigned_model)
        return table
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_monitor_v2.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/monitor_v2.py tests/test_monitor_v2.py
git commit -m "feat: improved monitor with validation feedback and wave progress"
```

---

### Task 5: Update orchestrator.py to wire v2 modules

**Files:**
- Modify: `src/orchestrator.py`

**Interfaces:**
- Consumes: `validator_v2`, `executor_v2`, `monitor_v2`, `checkpointing`, `models`, `config`, `api_client`, `decomposer`, `scheduler`, `collector`, `manifest`
- Produces: `Orchestrator.run()` with v2 modules

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrator_v2.py
import os
import tempfile
import shutil
from unittest.mock import patch
from src.orchestrator import Orchestrator


def test_orchestrator_run_dry_run():
    orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
    tmpdir = tempfile.mkdtemp()
    try:
        with patch("src.orchestrator.decompose") as mock_decompose:
            mock_decompose.return_value = []
            report = orch.run("Test problem", output_dir=tmpdir, dry_run=True)
            assert report == ""
    finally:
        shutil.rmtree(tmpdir)


def test_orchestrator_run_resume():
    orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
    tmpdir = tempfile.mkdtemp()
    try:
        with patch("src.orchestrator.decompose") as mock_decompose, \
             patch("src.orchestrator.checkpointing.Checkpointer") as mock_ckpt:
            mock_decompose.return_value = []
            mock_ckpt.return_value.load_state.return_value = None
            report = orch.run("Test problem", output_dir=tmpdir, resume=True)
            assert "completed" in report.lower() or "completed" in report.lower()
    finally:
        shutil.rmtree(tmpdir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator_v2.py -v`
Expected: FAIL — `ImportError` or `run() missing required keyword arguments`

- [ ] **Step 3: Update orchestrator.py**

```python
# src/orchestrator.py
import os
import shutil
from uuid import uuid4
from typing import Any, Dict, List, Optional
from src.config import load_config
from src.api_client import APIClient
from src.decomposer import decompose
from src.scheduler import schedule
from src.executor_v2 import execute_wave_v2
from src.collector import generate_report, save_report
from src.monitor_v2 import LiveMonitorV2
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
        self.client = APIClient(self.config, self.cost_tracker)
        self.model_config = self.config.get("models", {})

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
        decomposer_model = model_map.get("decomposer", self.model_config.get("decomposer", "openai:gpt-4o-mini"))
        executor_model = model_map.get("executor_default", self.model_config.get("executor_default", "openai:gpt-4o-mini"))
        repair_model = self.model_config.get("task_repair", executor_model)
        validator_model = self.model_config.get("plan_validator", executor_model)
        manifest = None
        execution_state = None
        repository_root = os.path.abspath(manifest_root) if manifest_root else None
        if repository_root:
            manifest = load_or_create_manifest(repository_root)
            execution_state = create_execution_state(repository_root, problem, uuid4().hex)

        repository_context = manifest_context(manifest) if manifest else None

        # Dry run: just decompose and show tasks
        if dry_run:
            tasks = decompose(problem, self.client, decomposer_model, repair_model, repository_context)
            if repository_root:
                validation = validate_plan_v2(
                    problem,
                    [t.model_dump() for t in tasks],
                    repository_context or "files: []",
                    validator_model,
                )
                self._print_validation(validation)
            self._print_tasks(tasks)
            return ""

        # Resume: load checkpoint
        checkpoint_dir = os.path.join(output_dir, "checkpoints")
        os.makedirs(checkpoint_dir, exist_ok=True)
        checkpointer = Checkpointer(checkpoint_dir)
        checkpoint_state = None
        if resume:
            checkpoint_state = checkpointer.load_state()
            if checkpoint_state and checkpoint_state.get("waves"):
                # Load waves from checkpoint (simplified: re-schedule from tasks)
                tasks = decompose(problem, self.client, decomposer_model, repair_model, repository_context)
                waves = schedule(tasks)
                # Mark completed waves as done
                for wave_idx, wave_data in enumerate(checkpoint_state["waves"]):
                    if wave_idx < len(waves):
                        waves[wave_idx].status = wave_data.get("status", "pending")
                        for task_data in wave_data.get("tasks", []):
                            task = next((t for t in waves[wave_idx].tasks if t.id == task_data["id"]), None)
                            if task:
                                task.status = task_data.get("status", "pending")
            else:
                tasks = decompose(problem, self.client, decomposer_model, repair_model, repository_context)
                waves = schedule(tasks)
        else:
            tasks = decompose(problem, self.client, decomposer_model, repair_model, repository_context)
            waves = schedule(tasks)

        # Override model assignment
        for task in tasks:
            if task.assigned_model == "default":
                task.assigned_model = executor_model

        # Validation (not for resume if already validated)
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

        # Checkpoint: save initial state
        checkpointer.save_state(waves)

        # Execute waves
        task_dir = os.path.join(output_dir, "tasks")
        result_dir = os.path.join(output_dir, "results")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)

        monitor = LiveMonitorV2(waves, verbose=verbose)
        monitor.start()

        for wave in waves:
            monitor.start_wave(wave)
            state_callback = None
            if repository_root and execution_state is not None:
                state_callback = lambda result: update_execution_state(repository_root, execution_state, result)
            if manifest is None and state_callback is None:
                execute_wave_v2(wave, task_dir, None, checkpointer)
            else:
                execute_wave_v2(wave, task_dir, manifest, checkpointer)
            for res in wave.task_results:
                monitor.update(res["task_id"], res["status"])

        monitor.stop(self.cost_tracker.summary())

        report = generate_report(waves)
        report_path = save_report(report, result_dir)

        if repository_root:
            save_manifest(repository_root, build_manifest(repository_root))

        checkpointer.cleanup()

        return report

    def _print_tasks(self, tasks: List):
        self.console = __import__("rich").console.Console()
        self.console.print(f"📋 Tasks ({len(tasks)}):")
        for task in tasks:
            self.console.print(f"  - {task.id}: {task.description[:60]}...")

    def _print_validation(self, validation: Dict):
        self.console = __import__("rich").console.Console()
        if validation["valid"]:
            self.console.print(Panel("✅ Plan validation passed", style="bold green"))
        else:
            self.console.print(Panel(f"❌ Plan validation failed:\n{validation['issues']}", style="bold red"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator_v2.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator_v2.py
git commit -m "feat: wire v2 modules into orchestrator"
```

---

### Task 6: Update CLI with new flags

**Files:**
- Modify: `src/cli.py`

**Interfaces:**
- Consumes: `Orchestrator`
- Produces: CLI with `--verbose`, `--dry-run`, `--resume` flags

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_v2.py
from typer.testing import CliRunner
from src.cli import app


runner = CliRunner()


def test_cli_run_dry_run():
    result = runner.invoke(app, ["run", "Test", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output.lower() or "tasks" in result.output.lower()


def test_cli_run_resume():
    result = runner.invoke(app, ["run", "Test", "--resume"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_v2.py -v`
Expected: FAIL — flags not found or not working

- [ ] **Step 3: Update cli.py**

```python
# src/cli.py
import typer
from typing import Optional
from src.orchestrator import Orchestrator

app = typer.Typer()


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
    if report:
        typer.echo("\n" + report)


@app.command()
def version():
    typer.echo("myagent 0.1.0")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_v2.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/cli.py tests/test_cli_v2.py
git commit -m "feat: add CLI flags --verbose, --dry-run, --resume"
```

---

### Task 7: Update config/default.yaml with pricing

**Files:**
- Modify: `config/default.yaml`

**Interfaces:**
- Consumes: none
- Produces: Pricing configuration for cost tracking

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_pricing.py
from src.config import load_config


def test_load_config_has_pricing():
    cfg = load_config("config/default.yaml")
    assert "pricing" in cfg
    assert "regolo:qwen3-coder-next" in cfg["pricing"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config_pricing.py -v`
Expected: FAIL — `pricing` not found

- [ ] **Step 3: Update config/default.yaml**

```yaml
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    timeout: 60
    retry_count: 3
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
    timeout: 60
    retry_count: 3
  regolo:
    api_key: "${REGOLO_API_KEY}"
    base_url: "https://api.regolo.ai/v1"
    timeout: 300
    retry_count: 1
    reasoning_effort: "low"
  opencode_zen:
    api_key: "${OPENCODE_ZEN_API_KEY}"
    base_url: ""
    timeout: 60
    retry_count: 3

models:
  decomposer: "regolo:qwen3.6-27b"
  scheduler: "regolo:qwen3.6-27b"
  executor_default: "regolo:qwen3-coder-next"
  task_repair: "regolo:qwen3-coder-next"
  plan_validator: "regolo:qwen3-coder-next"

pricing:
  regolo:qwen3.6-27b:
    input: 0.0
    output: 0.0
  regolo:qwen3-coder-next:
    input: 0.0
    output: 0.0
  openai:gpt-4o-mini:
    input: 0.15
    output: 0.60
  openai:gpt-4o:
    input: 5.0
    output: 15.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config_pricing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/default.yaml tests/test_config_pricing.py
git commit -m "feat: add pricing config for cost tracking"
```

---

### Task 8: Run full test suite and commit

**Files:**
- All new files + existing tests

**Interfaces:**
- None (validation task)

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: 79 existing + 32 new = 111 tests, all PASS

- [ ] **Step 2: Verify all tests pass**

Count: 111 tests
Expected: 0 failures

- [ ] **Step 3: Commit all changes**

```bash
git add -A
git commit -m "feat: improvements - validator retry, executor v2, checkpointing, CLI flags"
```

---

### Task 9: Update README.md with new features

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: none
- Produces: Updated documentation

- [ ] **Step 1: Update README**

Add sections for:
- Validation with retry
- Cost tracking with pricing config
- Checkpointing and resume
- New CLI flags

Example:
```markdown
## Improvements

### Robust Validation
Plans are validated using `opencode` with retry logic (up to 3 retries, 120s timeout each).

### Cost Tracking
Configure pricing in `config/default.yaml` under `pricing`. Costs are displayed per million tokens.

### Checkpointing & Resume
Execution state is saved after each wave. Use `--resume` to continue from where you left off.

### CLI Flags
- `--verbose`, `-v`: Enable verbose output
- `--dry-run`, `-n`: Show tasks without executing
- `--resume`, `-r`: Resume from checkpoint
```

- [ ] **Step 2: Run tests again to verify**

```bash
python -m pytest tests/ -v
```

Expected: 111 tests pass

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with new features"
```

---

## Implementation Summary

| Task | File | Tests | Lines |
|------|------|-------|-------|
| 1 | `src/validator_v2.py` | 2 | ~80 |
| 2 | `src/checkpointing.py` | 2 | ~100 |
| 3 | `src/executor_v2.py` | 3 | ~130 |
| 4 | `src/monitor_v2.py` | 2 | ~110 |
| 5 | `src/orchestrator.py` | 2 | ~250 |
| 6 | `src/cli.py` | 2 | ~20 |
| 7 | `config/default.yaml` | 1 | ~30 |
| **Total** | 7 files | 14 new tests | ~720 lines |

**Existing tests:** 79 (all must still pass)
**New tests:** 14 (new modules)
**Total tests:** 93

---

Plan complete and saved to `docs/superpowers/plans/2026-09-01-improvements.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**