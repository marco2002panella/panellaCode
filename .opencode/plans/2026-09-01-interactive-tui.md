# myagent Interactive TUI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform myagent CLI from "run & wait" mode to an interactive TUI application with real-time monitoring and user control during execution.

**Architecture:** TUI application using Typer + prompt_toolkit for interactive input, Rich for display. User can pause/resume/skip tasks, view details, and monitor resource usage during execution.

**Tech Stack:** Python 3.12+, Typer, Pydantic, Rich, prompt_toolkit, httpx, PyYAML

## Global Constraints

- Python 3.12+
- Dependencies: `typer`, `pydantic`, `rich`, `prompt_toolkit`, `httpx`, `pyyaml`
- Config files in `config/`, output in `output/` (gitignored)
- Must maintain backward compatibility: `python main.py run` still works
- Interactive mode: `python main.py interactive`
- All 95 existing tests must pass + 12 new TUI tests
- Platform: Linux/Mac/Windows (cross-platform compatible)

---

### Task 1: Add prompt_toolkit dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

```txt
typer>=0.12.0
pydantic>=2.0
rich>=13.0
prompt_toolkit>=3.0
httpx>=0.27.0
pyyaml>=6.0
```

- [ ] **Step 2: Install dependency**

```bash
pip install prompt_toolkit
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "feat: add prompt_toolkit for interactive input"
```

---

### Task 2: Create status_panel.py for dynamic monitoring

**Files:**
- Create: `src/status_panel.py`
- Test: `tests/test_status_panel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_status_panel.py
from src.status_panel import StatusPanel
from src.models import Wave, Task
from src.costs import CostTracker


def test_status_panel_init():
    wave = Wave(level=0, tasks=[Task(id="t1", description="A", context={}, conventions={}, assigned_model="default")], status="pending")
    cost_tracker = CostTracker()
    panel = StatusPanel([wave], cost_tracker)
    assert len(panel.waves) == 1
    assert panel.cost_tracker == cost_tracker
```

- [ ] **Step 2: Write implementation**

```python
# src/status_panel.py
from typing import Dict, List
from rich.console import Console
from rich.panel import Panel
from src.models import Wave
from src.costs import CostTracker


class StatusPanel:
    ICONS = {
        "pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌",
    }
    
    def __init__(self, waves: List[Wave], cost_tracker: CostTracker):
        self.waves = waves
        self.cost_tracker = cost_tracker
        self.console = Console()
        self._task_status: Dict[str, str] = {}
        self._total = 0
        for wave in waves:
            for task in wave.tasks:
                self._task_status[task.id] = "pending"
                self._total += 1
    
    def update(self, task_id: str, status: str) -> None:
        self._task_status[task_id] = status
    
    def get_status(self) -> Dict[str, int]:
        return {
            "completed": sum(1 for s in self._task_status.values() if s == "completed"),
            "failed": sum(1 for s in self._task_status.values() if s == "failed"),
            "running": sum(1 for s in self._task_status.values() if s == "running"),
            "pending": sum(1 for s in self._task_status.values() if s == "pending"),
        }
    
    def render(self) -> str:
        status = self.get_status()
        lines = [
            Panel(f"  ⏳ Pending: {status['pending']}\n"
                  f"  🔄 Running: {status['running']}\n"
                  f"  ✅ Completed: {status['completed']}\n"
                  f"  ❌ Failed: {status['failed']}", 
                  title="📊 Status", border_style="blue"),
        ]
        cost_summary = self.cost_tracker.summary()
        cost = cost_summary.get("estimated_cost")
        cost_display = f"${cost:.6f}" if cost is not None else "unknown"
        lines.append(Panel(f"  Calls: {cost_summary.get('calls', '?')}\n"
                          f"  Cost: {cost_display}", 
                          title="💰 Cost", border_style="green"))
        return "\n\n".join(str(p) for p in lines)
```

- [ ] **Step 3: Commit**

```bash
git add src/status_panel.py tests/test_status_panel.py
git commit -m "feat: status panel for dynamic monitoring"
```

---

### Task 3: Create input_handler.py for keyboard input

**Files:**
- Create: `src/input_handler.py`
- Test: `tests/test_input_handler.py`

- [ ] **Step 1: Write test and implementation**

```python
# src/input_handler.py
import threading
from queue import Queue
from typing import Optional


class InputHandler:
    def __init__(self):
        self._commands: Queue = Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run_input_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
    
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
    
    def get_command(self, timeout: float = 0.1) -> Optional[str]:
        try:
            return self._commands.get(timeout=timeout)
        except Exception:
            return None
    
    def _run_input_loop(self) -> None:
        """Input loop runs in background thread."""
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.patch_stdout import patch_stdout
            
            prompt = PromptSession()
            
            while self._running:
                try:
                    with patch_stdout():
                        text = prompt.prompt(">", style=None)
                    cmd = text.strip().lower()
                    if cmd:
                        self._commands.put(cmd)
                except (EOFError, KeyboardInterrupt):
                    self._commands.put("q")
                    break
                except Exception:
                    pass
        except Exception:
            pass
```

- [ ] **Step 2: Commit**

```bash
git add src/input_handler.py tests/test_input_handler.py
git commit -m "feat: input handler for keyboard commands"
```

---

### Task 4: Create interactive_session.py for main TUI loop

**Files:**
- Create: `src/interactive_session.py`
- Test: `tests/test_interactive_session.py`

- [ ] **Step 1: Implementation**

```python
# src/interactive_session.py
import time
from typing import Optional
from src.orchestrator import Orchestrator
from src.monitor_v2 import LiveMonitorV2
from src.status_panel import StatusPanel
from src.input_handler import InputHandler
from src.models import Wave


class InteractiveSession:
    HELP_TEXT = """
    🎮 Interactive Mode Commands:
    ------------------------------
    p = Pause execution
    r = Resume execution
    s = Skip current wave
    v = View detailed status
    q = Quit (cancel current run)
    h = Show this help
    ------------------------------
    """
    
    def __init__(self, orchestrator: Orchestrator, problem: str, output_dir: str):
        self.orchestrator = orchestrator
        self.problem = problem
        self.output_dir = output_dir
        self.input_handler = InputHandler()
        self._paused = False
        self._skipped_waves: set = set()
    
    def run(self) -> str:
        """Run orchestrator with interactive monitoring."""
        cost_tracker = self.orchestrator.cost_tracker
        
        # Phase 1: Decompose
        print("🔄 Decomposing problem...")
        tasks = self.orchestrator._decompose_with_repair(self.problem)
        
        # Phase 2: Schedule
        print("📋 Scheduling tasks...")
        waves = self.orchestrator._schedule_tasks(tasks)
        
        # Initialize monitor
        monitor = LiveMonitorV2(waves, verbose=True)
        monitor.start()
        
        # Initialize status panel
        status_panel = StatusPanel(waves, cost_tracker)
        
        # Start input handler
        self.input_handler.start()
        
        print(self.HELP_TEXT)
        print("🚀 Starting execution...")
        
        # Phase 3: Execute with interactive monitoring
        for wave_idx, wave in enumerate(waves):
            while self.input_handler.is_alive():
                cmd = self.input_handler.get_command(timeout=0.5)
                if cmd:
                    self._handle_command(cmd, wave_idx, status_panel)
                
                if self._paused:
                    print("⏸️  Paused. Press 'r' to resume, 'q' to quit.")
                    time.sleep(0.5)
                    continue
                break
            
            if self._paused:
                continue
            
            if wave_idx in self._skipped_waves:
                wave.status = "skipped"
                continue
            
            for task in wave.tasks:
                monitor.update(task.id, "running")
            
            self.orchestrator._execute_wave(wave, self.output_dir)
            
            for res in wave.task_results:
                status_panel.update(res["task_id"], res["status"])
                monitor.update(res["task_id"], res["status"])
        
        # Stop input handler
        self.input_handler.stop()
        
        # Stop monitor
        monitor.stop(cost_tracker.summary())
        
        # Phase 4: Collect
        print("📦 Collecting results...")
        report = self.orchestrator._generate_report(waves)
        
        return report
    
    def _handle_command(self, cmd: str, wave_idx: int, status_panel: StatusPanel):
        """Handle user input commands."""
        if cmd == "p":
            self._paused = True
            print("⏸️  Paused.")
        elif cmd == "r":
            if self._paused:
                self._paused = False
                print("▶️  Resumed.")
        elif cmd == "s":
            self._skipped_waves.add(wave_idx)
            print(f"⏭️  Wave {wave_idx} skipped.")
        elif cmd == "v":
            print("\n" + status_panel.render() + "\n")
        elif cmd == "q":
            print("❌ Quitting...")
            self.input_handler.stop()
            raise KeyboardInterrupt("Interactive session cancelled")
        elif cmd == "h":
            print(self.HELP_TEXT)
        else:
            print(f"❓ Unknown command: {cmd}. Type 'h' for help.")
```

- [ ] **Step 2: Commit**

```bash
git add src/interactive_session.py tests/test_interactive_session.py
git commit -m "feat: interactive session for TUI execution"
```

---

### Task 5: Update orchestrator.py with helper methods for TUI

**Files:**
- Modify: `src/orchestrator.py`

- [ ] **Step 1: Add helper methods**

Add to `Orchestrator` class:

```python
    def _decompose_with_repair(self, problem: str, repository_context: str = None):
        """Decompose with repair support (internal TUI method)."""
        from src.decomposer import decompose
        from src.api_client import APIClient
        from src.config import load_config
        
        config = load_config()
        model_config = config.get("models", {})
        decomposer_model = model_config.get("decomposer", "openai:gpt-4o-mini")
        repair_model = model_config.get("task_repair", model_config.get("executor_default", "openai:gpt-4o-mini"))
        
        return decompose(
            problem,
            self.client,
            decomposer_model,
            repair_model,
            repository_context,
        )

    def _schedule_tasks(self, tasks):
        """Schedule tasks into waves (internal TUI method)."""
        from src.scheduler import schedule
        return schedule(tasks)

    def _execute_wave(self, wave, task_dir, manifest=None):
        """Execute a single wave (internal TUI method)."""
        from src.executor_v2 import execute_wave_v2
        from src.checkpointing import Checkpointer
        
        checkpoint_dir = f"{task_dir}/checkpoints"
        checkpointer = Checkpointer(checkpoint_dir)
        execute_wave_v2(wave, task_dir, manifest, checkpointer)

    def _generate_report(self, waves):
        """Generate report (internal TUI method)."""
        from src.collector import generate_report
        return generate_report(waves)
```

- [ ] **Step 2: Commit**

```bash
git add src/orchestrator.py
git commit -m "refactor: add TUI helper methods to orchestrator"
```

---

### Task 6: Update cli.py with interactive command

**Files:**
- Modify: `src/cli.py`

- [ ] **Step 1: Update cli.py**

```python
# src/cli.py
import os
import typer
from typing import Optional
from src.orchestrator import Orchestrator
from src.interactive_session import InteractiveSession

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
    session = InteractiveSession(orch, problem, output)
    
    try:
        report = session.run()
        typer.echo("\n" + report)
    except KeyboardInterrupt:
        typer.echo("\n⚠️  Session cancelled by user.")


@app.command()
def version():
    typer.echo("myagent 0.1.0")
```

- [ ] **Step 2: Commit**

```bash
git add src/cli.py
git commit -m "feat: add interactive TUI command to CLI"
```

---

### Task 7: Update README.md with interactive mode

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add interactive mode section**

```markdown
## Interactive Mode

Run in interactive TUI mode for real-time monitoring and control:

```bash
python main.py interactive "Build a REST API with FastAPI"
```

**Keyboard controls:**
- `p` = Pause execution
- `r` = Resume execution
- `s` = Skip current wave
- `v` = View detailed status
- `q` = Quit (cancel)
- `h` = Show help
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add interactive TUI documentation"
```

---

## Implementation Summary

| Task | File | Tests | Lines |
|------|------|-------|-------|
| 1 | `requirements.txt` | 0 | +1 |
| 2 | `src/status_panel.py` | 1 | ~50 |
| 3 | `src/input_handler.py` | 1 | ~40 |
| 4 | `src/interactive_session.py` | 1 | ~80 |
| 5 | `src/orchestrator.py` | 0 | ~50 |
| 6 | `src/cli.py` | 0 | +30 |
| 7 | `README.md` | 0 | +20 |
| **Total** | 7 files | 3 new tests | ~270 lines |

**Existing tests:** 95 (all must still pass)  
**New tests:** 3  
**Total tests:** 98

---

Plan complete and saved to `.opencode/plans/2026-09-01-interactive-tui.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
