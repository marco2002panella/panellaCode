import os
import subprocess
import tempfile
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict

from src.models import Task, Wave
from src.manifest import ensure_manifest_header, manifest_context


def to_opencode_model(model_spec: str) -> str:
    provider, model = model_spec.split(":", 1)
    provider_aliases = {"regolo": "regolo-ai"}
    return f"{provider_aliases.get(provider, provider)}/{model}"


def write_task_file(task: Task, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{task.id}.yaml")
    with open(path, "w") as f:
        yaml.dump({
            "id": task.id,
            "description": task.description,
            "context": task.context,
            "conventions": task.conventions,
            "dependencies": task.dependencies,
            "level": task.level,
            "assigned_model": task.assigned_model,
        }, f, default_flow_style=False)
    return path


def build_opencode_prompt(task: Task, manifest: Dict = None) -> str:
    prompt = (
        f"You are given a task to complete.\n\n"
        f"Task ID: {task.id}\n"
        f"Description: {task.description}\n\n"
        f"Context:\n"
        f"  Project root: {task.context.get('project_root', 'N/A')}\n"
        f"  Output file: {task.context.get('output_file', 'N/A')}\n"
        f"  Related files: {task.context.get('related_files', [])}\n\n"
        f"Conventions:\n"
        f"  Framework: {task.conventions.get('framework', 'N/A')}\n"
        f"  Language: {task.conventions.get('language', 'N/A')}\n"
        f"  Style: {task.conventions.get('style', 'N/A')}\n"
        f"  Code split: {task.conventions.get('code_split', [])}\n\n"
        f"Complete this task and write your output to the specified file."
    )
    if manifest:
        prompt += f"\n\nRepository manifest:\n{manifest_context(manifest)}"
    return prompt


def execute_task(task: Task, output_dir: str, manifest: Dict = None) -> Dict:
    task_file = write_task_file(task, output_dir)
    prompt = build_opencode_prompt(task, manifest)
    result_path = os.path.join(output_dir, f"{task.id}_result.md")
    result = {
        "task_id": task.id,
        "task_file": task_file,
        "result_path": result_path,
        "status": "pending",
        "error": None,
    }
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as pf:
            pf.write(prompt)
            prompt_file = pf.name

        model = to_opencode_model(task.assigned_model)
        cmd = [
            "opencode",
            "run",
            "--model",
            model,
            "Complete the attached task and write the requested output.",
            "--file",
            prompt_file,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        os.unlink(prompt_file)

        if proc.returncode == 0 and proc.stdout.strip():
            result["status"] = "completed"
            with open(result_path, "w") as f:
                f.write(proc.stdout)
            if task.output_file:
                output_file = os.path.abspath(task.output_file)
                ensure_manifest_header(
                    output_file,
                    task.output_file,
                    task.description,
                )
        elif proc.returncode == 0:
            result["status"] = "failed"
            result["error"] = "opencode returned empty output"
        else:
            result["status"] = "failed"
            result["error"] = proc.stderr
    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["error"] = "Task timed out (300s)"
    except FileNotFoundError:
        result["status"] = "failed"
        result["error"] = "opencode command not found"
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)

    return result


def execute_wave(wave: Wave, output_dir: str) -> Wave:
    wave.status = "running"
    results = []
    for task in wave.tasks:
        print(f"  Executing {task.id} (model: {task.assigned_model})...")
        res = execute_task(task, output_dir)
        results.append(res)
        print(f"  {task.id}: {res['status']}")
    wave.status = "completed" if all(r["status"] == "completed" for r in results) else "failed"
    wave.task_results = results
    return wave


def execute_wave_parallel(
    wave: Wave,
    output_dir: str,
    manifest: Dict = None,
    state_callback=None,
) -> Wave:
    if not wave.tasks:
        wave.status = "completed"
        wave.task_results = []
        return wave

    wave.status = "running"
    results = []
    with ThreadPoolExecutor(max_workers=len(wave.tasks)) as executor:
        submit = (
            lambda task: executor.submit(execute_task, task, output_dir)
            if manifest is None
            else executor.submit(execute_task, task, output_dir, manifest)
        )
        future_to_task = {
            submit(task): task
            for task in wave.tasks
        }
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                res = future.result()
                results.append(res)
                if state_callback:
                    state_callback(res)
                print(f"  {task.id}: {res['status']}")
            except Exception as e:
                results.append({
                    "task_id": task.id,
                    "status": "failed",
                    "error": str(e),
                })
                if state_callback:
                    state_callback(results[-1])
                print(f"  {task.id}: failed — {e}")

    wave.status = "completed" if all(r["status"] == "completed" for r in results) else "failed"
    wave.task_results = results
    return wave
