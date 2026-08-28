import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List

from src.executor import to_opencode_model


def _parse_json_output(output: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(output.strip())
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    for line in reversed(output.splitlines()):
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict) and "valid" in parsed:
                return parsed
        except json.JSONDecodeError:
            continue
    raise ValueError("validator returned invalid JSON")


def validate_plan(problem: str, tasks: List[Dict], manifest: str, model_spec: str) -> Dict[str, Any]:
    prompt = (
        "Validate the following task plan against the original problem and repository manifest. "
        "Return JSON only with keys valid (boolean), issues (array), and missing_tasks (array). "
        "Check semantic completeness, not just YAML syntax.\n\n"
        f"Original problem:\n{problem}\n\nTask plan:\n{json.dumps(tasks, indent=2)}\n\n"
        f"Repository manifest:\n{manifest}"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as stream:
        stream.write(prompt)
        prompt_file = stream.name
    try:
        process = subprocess.run(
            [
                "opencode",
                "run",
                "--format",
                "json",
                "--model",
                to_opencode_model(model_spec),
                "Validate the attached task plan and return JSON only.",
                "--file",
                prompt_file,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return {"valid": False, "issues": [str(error)], "missing_tasks": []}
    finally:
        os.unlink(prompt_file)

    if process.returncode != 0:
        return {"valid": False, "issues": [process.stderr.strip() or "validator failed"], "missing_tasks": []}
    try:
        result = _parse_json_output(process.stdout)
    except ValueError as error:
        return {"valid": False, "issues": [str(error)], "missing_tasks": []}
    result.setdefault("issues", [])
    result.setdefault("missing_tasks", [])
    result["valid"] = bool(result.get("valid", False))
    return result
