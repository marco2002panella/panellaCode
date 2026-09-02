# src/tui/run_tui.py
"""Entrypoint for the problemSolver GUI: wires an Orchestrator, a
TUIEventBridge and the AgentTUI App, then runs the App."""

from typing import Optional

from src.orchestrator import Orchestrator
from src.tui.app import AgentTUI
from src.tui.bridge import TUIEventBridge


def run_gui(config: str = "config/default.yaml") -> None:
    orchestrator = Orchestrator(config_path=config)
    bridge = TUIEventBridge()
    app = AgentTUI()
    app.attach(bridge, orchestrator)
    app.options.config = config
    app.run()