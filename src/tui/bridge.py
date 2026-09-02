# src/tui/bridge.py
"""Thread-safe bridge between the TUI event loop and the worker thread.

Worker -> UI : events (decompose_started, validation_result, wave_started,
               task_started, task_output, task_done, run_done, error)
UI -> worker  : commands (pause, resume, skip, quit)
"""

import threading
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any, Dict, List, Optional


@dataclass
class TUIEvent:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)


class TUIEventBridge:
    def __init__(self):
        self._events: Queue = Queue()
        self._commands: Queue = Queue()
        self._paused = threading.Event()
        self._quit = threading.Event()
        self._skip_wave = threading.Event()

    # ---- worker -> UI ----
    def emit(self, type: str, **payload) -> None:
        self._events.put(TUIEvent(type, payload))

    def next_event(self, timeout: float = 0) -> Optional[TUIEvent]:
        try:
            return self._events.get(timeout=timeout)
        except Empty:
            return None

    def drain_events(self, max_items: int = 100) -> List[TUIEvent]:
        out: List[TUIEvent] = []
        while len(out) < max_items:
            ev = self.next_event(timeout=0)
            if ev is None:
                break
            out.append(ev)
        return out

    # ---- UI -> worker ----
    def send_command(self, type: str, **payload) -> None:
        self._commands.put(TUIEvent(type, payload))

    def next_command(self, timeout: float = 0) -> Optional[TUIEvent]:
        try:
            return self._commands.get(timeout=timeout)
        except Empty:
            return None

    # ---- control flags (polled by workers between tasks/waves) ----
    def set_paused(self, paused: bool) -> None:
        if paused:
            self._paused.set()
        else:
            self._paused.clear()

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def request_skip_wave(self) -> None:
        self._skip_wave.set()

    def drain_skip(self) -> bool:
        if self._skip_wave.is_set():
            self._skip_wave.clear()
            return True
        return False

    def request_quit(self) -> None:
        self._quit.set()

    def is_quit_requested(self) -> bool:
        return self._quit.is_set()