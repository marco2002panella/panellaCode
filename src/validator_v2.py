import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List


def validate_plan_v2(
    problem: str,
    tasks: List[Dict],
    manifest: str,
    model: str,
    timeout: int = 120,
    max_retries: int = 3,
) -> Dict[str, Any]:
    prompt = (
        "Validate the following task plan against the original problem and repository manifest. "
        "Return JSON only with keys valid (boolean), issues (array), and missing_tasks (array).\n\n"
        f"Original problem:\n{problem}\n\nTask plan:\n{json.dumps(tasks, indent=2)}\n\n"
        f"Repository manifest:\n{manifest}"
    )

    last_error = None
    for attempt in range(max_retries):
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
                    model.replace(":", "/"),
                    "Validate the attached task plan and return JSON only.",
                    "--file",
                    prompt_file,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            os.unlink(prompt_file)

            if process.returncode == 0:
                try:
                    parsed = json.loads(process.stdout.strip())
                    if isinstance(parsed, dict) and "valid" in parsed:
                        return parsed
                except json.JSONDecodeError:
                    for line in reversed(process.stdout.splitlines()):
                        try:
                            parsed = json.loads(line)
                            if isinstance(parsed, dict) and "valid" in parsed:
                                return parsed
                        except json.JSONDecodeError:
                            continue

            last_error = process.stderr.strip() or "validator returned invalid output"
        except subprocess.TimeoutExpired:
            last_error = "validator timed out"
        except FileNotFoundError:
            return {"valid": False, "issues": ["opencode command not found"], "missing_tasks": []}
        finally:
            if os.path.exists(prompt_file):
                os.unlink(prompt_file)

    return {"valid": False, "issues": [f"validator failed after {max_retries} retries: {last_error}"], "missing_tasks": []}