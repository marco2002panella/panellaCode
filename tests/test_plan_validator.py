from unittest.mock import MagicMock, patch

from src.plan_validator import validate_plan


def test_validate_plan_parses_json_response():
    completed = MagicMock(returncode=0, stdout='{"valid": true, "issues": []}', stderr="")
    tasks = [{"id": "task_001", "description": "Build app", "output_file": "main.py"}]

    with patch("src.plan_validator.subprocess.run", return_value=completed):
        result = validate_plan("Build an app", tasks, "files: []", "regolo:qwen3-coder-next")

    assert result["valid"] is True
    assert result["issues"] == []


def test_validate_plan_fails_closed_on_invalid_output():
    completed = MagicMock(returncode=0, stdout="not json", stderr="")
    with patch("src.plan_validator.subprocess.run", return_value=completed):
        result = validate_plan("Build an app", [], "files: []", "regolo:qwen3-coder-next")

    assert result["valid"] is False
    assert "JSON" in result["issues"][0]
