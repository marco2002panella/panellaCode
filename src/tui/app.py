# src/tui/app.py
"""problemSolver TUI application (Textual).

Flow: type a problem at the top -> Enter -> the worker thread decomposes,
validates, schedules and executes waves with live streaming. The UI polls
the TUIEventBridge every ~100ms and refreshes the four panels. The problem
input freezes while a run is active and reactivates on RunDone for the next
problem in the same session.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from src.tui.bridge import TUIEventBridge
from src.tui.panels import (
    CostPanel,
    LogPanel,
    OptionsState,
    ResultPanel,
    WavePanel,
    task_result_content,
)


class OptionsScreen(Screen):
    """Modal settings: edit manifest/output/models, saved on Enter."""

    BINDINGS = [("escape", "close_options", "Close")]

    def __init__(self, options: OptionsState, **kwargs):
        super().__init__(**kwargs)
        self.current = options

    def compose(self) -> ComposeResult:
        with Vertical(id="options-screen"):
            yield Static("Options (problemSolver)", id="options-title")
            for field in ("manifest", "output", "config", "decomposer_model", "executor_model"):
                yield Static(field.replace("_", " ").capitalize() + ":", id=f"opt-label-{field}")
            self.inputs = {}
            for field in self.current.to_dict():
                self.inputs[field] = Input(
                    value=str(getattr(self.current, field)),
                    placeholder=field,
                    id=f"opt-{field}",
                )
                yield self.inputs[field]

    def action_close_options(self) -> None:
        for field, inp in self.inputs.items():
            attr = getattr(self.current, field)
            if isinstance(attr, bool):
                continue
            cls = type(attr)
            try:
                setattr(self.current, field, cls(inp.value))
            except (TypeError, ValueError):
                pass
        self.app.pop_screen()


class AgentTUI(App):
    TITLE = "problemSolver"
    SUB_TITLE = "type a problem, press Enter"

    BINDINGS = [
        Binding("p", "toggle_pause", "Pause"),
        Binding("r", "resume", "Resume"),
        Binding("s", "skip_task", "Skip"),
        Binding("v", "focus_result", "View result"),
        Binding("o", "open_options", "Options"),
        Binding("q", "quit_run", "Quit"),
    ]

    CSS = """
    #input-row {
        height: 3;
        padding: 0 1;
    }
    #grid {
        height: 1fr;
    }
    #wave-panel, #log-panel, #result-panel, #cost-panel {
        border: round $primary;
        height: 1fr;
        padding: 0 1;
    }
    """

    def __init__(self, problem_input: Optional[str] = None, **kwargs):
        """problem_input: if set, debounce direct launch is not used by tests."""
        super().__init__(**kwargs)
        self.bridge: Optional[TUIEventBridge] = None
        self.orchestrator = None
        self.options = OptionsState()
        self.problem_input_widget: Optional[Input] = None
        self.wave_panel = WavePanel()
        self.log_panel = LogPanel()
        self.result_panel = ResultPanel()
        self.cost_panel = CostPanel()
        self._wave_static: Optional[Static] = None
        self._log_static: Optional[Static] = None
        self._result_static: Optional[Static] = None
        self._cost_static: Optional[Static] = None
        self._running = False
        self._paused = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="problemsolver-worker")

    def attach(self, bridge: TUIEventBridge, orchestrator) -> None:
        self.bridge = bridge
        self.orchestrator = orchestrator
        self.options.output = os.path.join(self.orchestrator.config.get("output", "output"))
        self.options.decomposer_model = self.orchestrator.model_config.get("decomposer", self.options.decomposer_model)
        self.options.executor_model = self.orchestrator.model_config.get("executor_default", self.options.executor_model)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="input-row"):
            self.problem_input_widget = Input(placeholder="Descrivi il problema...", id="problem-input")
            yield self.problem_input_widget
        with Container(id="grid"):
            yield Static(self.wave_panel.renderable(), id="wave-panel")
            yield Static(self.log_panel.renderable(), id="log-panel")
            yield Static(self.result_panel.renderable(), id="result-panel")
            yield Static(self.cost_panel.renderable(), id="cost-panel")
        yield Footer()

    def on_mount(self):
        self.set_interval(0.1, self._poll_events)
        self._capture_panels()
        if self.problem_input_widget:
            self.problem_input_widget.focus()

    def _capture_panels(self):
        self._wave_static = self.query_one("#wave-panel", Static)
        self._log_static = self.query_one("#log-panel", Static)
        self._result_static = self.query_one("#result-panel", Static)
        self._cost_static = self.query_one("#cost-panel", Static)

        self._cost_refresh()

    def _refresh_statics(self):
        if self._wave_static:
            self._wave_static.update(self.wave_panel.renderable())
        if self._log_static:
            self._log_static.update(self.log_panel.renderable())
        if self._result_static:
            self._result_static.update(self.result_panel.renderable())
        if self._cost_static:
            self._cost_static.update(self.cost_panel.renderable())

    def _cost_refresh(self):
        if self.orchestrator and self.orchestrator.cost_tracker:
            self.cost_panel.set_summary(self.orchestrator.cost_tracker.summary())

    # ---- lifecycle / event polling ----
    def on_input_submitted(self, event: Input.Submitted) -> None:
        problem = (event.value or "").strip()
        if problem and not self._running:
            self._start_run(problem)

    def _start_run(self, problem: str) -> None:
        self._running = True
        self._paused = False
        if self.problem_input_widget:
            self.problem_input_widget.disabled = True
            self.problem_input_widget.value = ""
        self.wave_panel.clear()
        self.log_panel.clear()
        self.result_panel.clear()
        self.bridge.emit("run_started", problem=problem)
        self._executor.submit(self._worker, problem)

    def _worker(self, problem: str) -> None:
        try:
            tasks = self.orchestrator._decompose_with_repair(
                problem, self.options.manifest, decomposer_model=self.options.decomposer_model,
            )
        except Exception as e:
            self.bridge.emit("error", message=str(e))
            return
        self.bridge.emit("decompose_done")
        try:
            self.orchestrator._assign_default_models(tasks, self.options.executor_model)
        except Exception as e:
            self.bridge.emit("error", message=str(e))
            return
        waves = self.orchestrator._schedule_tasks(tasks)
        for task in tasks:
            self.wave_panel.add_task(task.id, task.assigned_model)
        self.bridge.emit("waves_scheduled", count=len(tasks))

        task_dir = os.path.join(self.options.output, "tasks")
        os.makedirs(task_dir, exist_ok=True)
        manifest = None
        repository_root = os.path.abspath(self.options.manifest) if self.options.manifest else None
        if repository_root:
            from src.manifest import load_or_create_manifest
            manifest = load_or_create_manifest(repository_root)

        for wave in waves:
            if self.bridge.is_quit_requested():
                break
            self.bridge.emit("wave_started", level=wave.level)
            self.orchestrator._execute_wave_stream(
                wave,
                task_dir,
                manifest,
                checkpointer=None,
                on_output=lambda task_id, line, is_stderr: self.bridge.emit(
                    "task_output", task_id=task_id, line=line, is_stderr=is_stderr,
                ),
                on_done=lambda result: self.bridge.emit(
                    "task_done",
                    task_id=result["task_id"],
                    status=result["status"],
                    result_path=result.get("result_path"),
                ),
            )

        if self.bridge.is_quit_requested():
            return

        report = self.orchestrator._generate_report(waves)
        self.bridge.emit("run_done", report=report)

    def _poll_events(self) -> None:
        if not self.bridge:
            return
        for ev in self.bridge.drain_events():
            self._handle_event(ev)
        self._cost_refresh()
        self._refresh_statics()

    def _handle_event(self, ev) -> None:
        t = ev.type
        p = ev.payload
        if t == "run_started":
            self.log_panel.append("▶ Run started", is_stderr=False)
        elif t == "decompose_done":
            self.log_panel.append("✓ Decomposed", is_stderr=False)
        elif t == "waves_scheduled":
            self.log_panel.append(f"✓ {p.get('count', 0)} tasks scheduled", is_stderr=False)
        elif t == "wave_started":
            self.log_panel.append(f"▶ Wave {p.get('level', '?')} started", is_stderr=False)
        elif t == "task_output":
            self.log_panel.append(p.get("line", ""), is_stderr=p.get("is_stderr", False))
        elif t == "task_done":
            status = p.get("status", "completed")
            self.wave_panel.on_task_done(p.get("task_id", ""), status)
            if status == "completed" and p.get("result_path"):
                self.result_panel.show(task_result_content(p.get("result_path")))
            self.log_panel.append(f"✓ {p.get('task_id', '')} {status}", is_stderr=False)
        elif t == "run_done":
            self.log_panel.append("✓ Run complete — input ready for next problem", is_stderr=False)
            self.result_panel.show(p.get("report", ""))
            self._running = False
            if self.problem_input_widget:
                self.problem_input_widget.disabled = False
                self.problem_input_widget.focus()
        elif t == "error":
            self.log_panel.append(f"✗ {p.get('message', 'error')}", is_stderr=True)
            self._running = False
            if self.problem_input_widget:
                self.problem_input_widget.disabled = False
                self.problem_input_widget.focus()

    # ---- key bindings ----
    def action_toggle_pause(self) -> None:
        if self._running and self.bridge:
            self._paused = not self._paused
            self.bridge.set_paused(self._paused)
            self.log_panel.append("⏸ paused" if self._paused else "▶ resumed", is_stderr=False)

    def action_resume(self) -> None:
        if self._running and self.bridge:
            self._paused = False
            self.bridge.set_paused(False)
            self.log_panel.append("▶ resumed", is_stderr=False)

    def action_skip_task(self) -> None:
        if self.bridge:
            self.bridge.send_command("skip", task_id="")

    def action_focus_result(self) -> None:
        if self._result_static:
            self._result_static.focus()

    def action_open_options(self) -> None:
        self.app.push_screen(OptionsScreen(self.options))

    def action_quit_run(self) -> None:
        if self.bridge:
            self.bridge.request_quit()
            self.log_panel.append("⏹ quitting...", is_stderr=False)
        self.exit()

    async def on_unmount(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=False)