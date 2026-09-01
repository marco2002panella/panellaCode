import subprocess
from unittest.mock import MagicMock, patch

from src.validator_v2 import validate_plan_v2


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