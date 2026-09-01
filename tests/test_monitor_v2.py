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