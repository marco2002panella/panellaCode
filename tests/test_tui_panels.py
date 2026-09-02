# tests/test_tui_panels.py
"""Panel state + text rendering, without mounting a real Textual App."""

from src.tui.panels import (
    CostPanel,
    LogPanel,
    OptionsState,
    ResultPanel,
    WavePanel,
)


def _lines(panel) -> str:
    return "\n".join(panel._render_lines())


def test_wave_panel_initial_state():
    panel = WavePanel()
    text = _lines(panel)
    assert "No tasks" in text or "Task" in text


def test_wave_panel_tracks_task_lifecycle():
    panel = WavePanel()
    panel.add_task("t1", "opencode_zen:big-pickle")
    panel.on_task_started("t1", "opencode_zen:big-pickle")
    panel.on_task_done("t1", "completed")

    text = _lines(panel)
    assert "t1" in text
    assert "completed" in text


def test_wave_panel_task_failed():
    panel = WavePanel()
    panel.add_task("t1", "m1")
    panel.on_task_done("t1", "failed")
    assert "failed" in _lines(panel)


def test_log_panel_appends_lines():
    panel = LogPanel()
    panel.append("first line", is_stderr=False)
    panel.append("second line", is_stderr=False)
    text = _lines(panel)
    assert "first line" in text
    assert "second line" in text


def test_log_panel_clear():
    panel = LogPanel()
    panel.append("gone", is_stderr=False)
    panel.clear()
    assert "gone" not in _lines(panel)


def test_result_panel_shows_text():
    panel = ResultPanel()
    panel.show("hello markdown")
    text = _lines(panel)
    assert "hello markdown" in text


def test_cost_panel_summary():
    panel = CostPanel()
    panel.set_summary({
        "calls": 12,
        "input_tokens": 45000,
        "output_tokens": 12000,
        "estimated_cost": 0.0,
        "unknown_calls": 0,
    })
    text = _lines(panel)
    assert "12" in text
    assert "45000" in text


def test_cost_panel_no_cost_yet():
    panel = CostPanel()
    assert isinstance(_lines(panel), str)


def test_options_state_defaults():
    opts = OptionsState()
    assert opts.manifest == "."
    assert opts.output == "output"
    assert opts.config == "config/default.yaml"
    assert opts.decomposer_model == "opencode_zen:big-pickle"
    assert opts.executor_model == "opencode_zen:big-pickle"


def test_options_state_roundtrip():
    opts = OptionsState(
        manifest="/repo", output="/out", config="config/c.yaml",
        decomposer_model="regolo:qwen3.8-27b",
        executor_model="regolo:qwen3-coder-next",
        verbose=True,
    )
    data = opts.to_dict()
    restored = OptionsState(**data)
    assert restored == opts