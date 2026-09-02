# src/tui/panels.py
"""Panel data models for the problemSolver TUI.

Each panel keeps its own state and can render either plain text lines
(`_render_lines`, used by tests) or a Rich renderable (`renderable`,
used by the Textual App). Keeping the state/rendering logic free of a
live Textual App makes the panels unit-testable in isolation.
"""

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from rich.table import Table
from rich.text import Text

_STATUS_ICON = {
    "pending": "○",
    "running": "⟳",
    "completed": "✓",
    "failed": "✗",
    "skipped": "⏭",
}


@dataclass
class OptionsState:
    manifest: str = "."
    output: str = "output"
    config: str = "config/default.yaml"
    decomposer_model: str = "opencode_zen:big-pickle"
    executor_model: str = "opencode_zen:big-pickle"
    verbose: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WavePanel:
    """Wave/task list: status, id, assigned model, execution time."""

    def __init__(self):
        self.rows: List[Dict[str, Any]] = []

    def add_task(self, task_id: str, model: str = "") -> None:
        if any(r["id"] == task_id for r in self.rows):
            return
        self.rows.append({
            "id": task_id,
            "status": "pending",
            "model": model,
            "time": "",
        })

    def on_task_started(self, task_id: str, model: str = "") -> None:
        row = self._row(task_id)
        if row:
            row["status"] = "running"
            row["model"] = model or row["model"]

    def on_task_done(self, task_id: str, status: str = "completed") -> None:
        row = self._row(task_id)
        if row:
            row["status"] = status

    def mark_wave(self, level: int, status: str) -> None:
        for row in self.rows:
            row["wave"] = level

    def clear(self) -> None:
        self.rows = []

    def _row(self, task_id: str) -> Optional[Dict[str, Any]]:
        return next((r for r in self.rows if r["id"] == task_id), None)

    def _render_lines(self) -> List[str]:
        if not self.rows:
            return ["No tasks yet."]
        lines = []
        for r in self.rows:
            icon = _STATUS_ICON.get(r["status"], r["status"])
            model = r.get("model") or "—"
            lines.append(f"{icon} {r['id']:<16} {r['status']:<12} {model}")
        return lines

    def renderable(self) -> Table:
        table = Table(title="Wave / Task", expand=True, show_header=True)
        table.add_column("#")
        table.add_column("Status")
        table.add_column("Task ID")
        table.add_column("Model")
        for idx, r in enumerate(self.rows, 1):
            table.add_row(
                str(idx),
                r["status"],
                r["id"],
                r.get("model") or "—",
            )
        if not self.rows:
            table.add_row("", "—", "No tasks yet", "")
        return table


class LogPanel:
    """Streaming log of executor (opencode run) output."""

    def __init__(self, max_lines: int = 500):
        self.lines: List[Tuple[str, bool]] = []  # (line, is_stderr)
        self.max_lines = max_lines

    def append(self, line: str, is_stderr: bool = False) -> None:
        self.lines.append((line, is_stderr))
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines:]

    def clear(self) -> None:
        self.lines = []

    def _render_lines(self) -> List[str]:
        out = []
        for line, is_stderr in self.lines:
            out.append(("[err] " if is_stderr else "") + line)
        return out[-300:]

    def renderable(self) -> Text:
        text = Text()
        for line, is_stderr in self.lines[-300:]:
            prefix = Text("[err] ", style="bold red") if is_stderr else Text()
            text.append_text(prefix)
            text.append(line + "\n")
        return text


class ResultPanel:
    """Viewer for the selected task result and the final report."""

    def __init__(self):
        self.text = ""

    def show(self, content: str) -> None:
        self.text = content or ""

    def clear(self) -> None:
        self.text = ""

    def _render_lines(self) -> List[str]:
        return self.text.splitlines() or ["—"]

    def renderable(self) -> Text:
        return Text(self.text if self.text else "—")


class CostPanel:
    """Live call/token/cost summary across models."""

    def __init__(self):
        self.summary: Dict[str, Any] = {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost": None,
            "unknown_calls": 0,
        }

    def set_summary(self, summary: Dict[str, Any]) -> None:
        self.summary.update(summary or {})

    def _render_lines(self) -> List[str]:
        s = self.summary
        cost = s.get("estimated_cost")
        cost_str = f"${cost:.6f}" if cost is not None else "unknown"
        return [
            f"calls: {s.get('calls', 0)}",
            f"tokens: {s.get('input_tokens', 0)} in / {s.get('output_tokens', 0)} out",
            f"est. cost: {cost_str}",
            f"unknown: {s.get('unknown_calls', 0)}",
        ]

    def renderable(self) -> Text:
        return Text("\n".join(self._render_lines()))


def task_result_content(result_path: Optional[str]) -> str:
    """Read a task result markdown file for the ResultPanel."""
    if not result_path or not os.path.isfile(result_path):
        return ""
    try:
        with open(result_path) as f:
            return f.read()
    except OSError:
        return ""