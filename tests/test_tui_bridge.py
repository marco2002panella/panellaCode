# tests/test_tui_bridge.py
import threading
import time

from src.tui.bridge import TUIEvent, TUIEventBridge


def test_emit_and_drain_events():
    bridge = TUIEventBridge()
    bridge.emit("task_started", task_id="t1")
    bridge.emit("task_output", task_id="t1", line="hello")
    bridge.emit("task_done", task_id="t1", status="completed")

    events = bridge.drain_events()
    assert [e.type for e in events] == ["task_started", "task_output", "task_done"]
    assert events[1].payload["line"] == "hello"


def test_next_event_timeout_returns_none():
    bridge = TUIEventBridge()
    assert bridge.next_event(timeout=0) is None


def test_commands_roundtrip():
    bridge = TUIEventBridge()
    bridge.send_command("skip", task_id="t2")
    cmd = bridge.next_command(timeout=0)
    assert cmd is not None
    assert cmd.type == "skip"
    assert cmd.payload["task_id"] == "t2"


def test_pause_resume_flags():
    bridge = TUIEventBridge()
    assert not bridge.is_paused()
    bridge.set_paused(True)
    assert bridge.is_paused()
    bridge.set_paused(False)
    assert not bridge.is_paused()


def test_skip_wave_flag_single_drain():
    bridge = TUIEventBridge()
    bridge.request_skip_wave()
    assert bridge.drain_skip() is True
    assert bridge.drain_skip() is False


def test_quit_flag():
    bridge = TUIEventBridge()
    assert not bridge.is_quit_requested()
    bridge.request_quit()
    assert bridge.is_quit_requested()


def test_bridge_is_thread_safe():
    bridge = TUIEventBridge()
    results = []

    def producer():
        for i in range(200):
            bridge.emit("task_output", task_id="tx", line=str(i))

    def consumer():
        got = 0
        deadline = time.time() + 5
        while got < 200 and time.time() < deadline:
            ev = bridge.next_event(timeout=0.01)
            if ev is not None:
                got += 1
        results.append(got)

    t_prod = threading.Thread(target=producer)
    t_cons = threading.Thread(target=consumer)
    t_prod.start()
    t_cons.start()
    t_prod.join()
    t_cons.join()
    assert results[0] == 200