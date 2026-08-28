import os
import subprocess
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict

from src.models import Task, Wave


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


def build_opencode_prompt(task: Task) -> str:
    return (
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


def execute_task(task: Task, output_dir: str) -> Dict:
    task_file = write_task_file(task, output_dir)
    prompt = build_opencode_prompt(task)
    result_path = os.path.join(output_dir, f"{task.id}_result.md")
    result = {
        "task_id": task.id,
        "task_file": task_file,
        "result_path": result_path,
        "status": "pending",
        "error": None,
    }

    try:
        proc = subprocess.run(
            ["opencode", "--model", task.assigned_model, prompt],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode == 0:
            result["status"] = "completed"
            with open(result_path, "w") as f:
                f.write(proc.stdout)
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


def execute_wave_parallel(wave: Wave, output_dir: str) -> Wave:
    if not wave.tasks:
        wave.status = "completed"
        wave.task_results = []
        return wave

    wave.status = "running"
    results = []

    with ThreadPoolExecutor(max_workers=len(wave.tasks)) as executor:
        future_to_task = {
            executor.submit(execute_task, task, output_dir): task
            for task in wave.tasks
        }
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                res = future.result()
                results.append(res)
                print(f"  {task.id}: {res['status']}")
            except Exception as e:
                results.append({
                    "task_id": task.id,
                    "status": "failed",
                    "error": str(e),
                })
                print(f"  {task.id}: failed — {e}")

    wave.status = "completed" if all(r["status"] == "completed" for r in results) else "failed"
    wave.task_results = results
    return wave