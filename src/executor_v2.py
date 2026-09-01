# src/executor_v2.py
import os
import subprocess
import tempfile
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from src.models import Task, Wave
from src.checkpointing import Checkpointer
from src.zen_router import ZenRouter, to_opencode_model


def build_executor_prompt(task: Task, manifest: Dict = None) -> str:
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
        f"Complete this task and write your output to the specified file.\n\n"
        f"VALIDATION REQUIREMENTS — PRIMA di dichiarare la task completata, DEVI:\n"
        f"1. Usare lo strumento `read` o `glob` per verificare che l'output file esista;\n"
        f"2. Usare `bash` per eseguire un check di sintassi/compilazione del file generato\n"
        f"   (es. `python -m py_compile <file>`, o il linter/test pertinente al language/stack);\n"
        f"3. Se la task lo richiede, eseguire i test (es. pytest) tramite `bash`;\n"
        f"4. Aggiungere al tuo output una sezione finale \"VALIDATION:\" che riporti i passi\n"
        f"   eseguiti e l'esito (PASS/FAIL) di ciascuno.\n"
        f"Non completare la task se la validazione fallisce: correggi il file e ricontrolla.\n"
    )
    if manifest:
        from src.manifest import manifest_context
        prompt += f"\n\nRepository manifest:\n{manifest_context(manifest)}"
    return prompt


def execute_task_v2(
    task: Task,
    output_dir: str,
    manifest: Dict = None,
    max_retries: int = 3,
    router: ZenRouter = None,
) -> Dict:
    task_file = os.path.join(output_dir, f"{task.id}.yaml")
    os.makedirs(output_dir, exist_ok=True)
    with open(task_file, "w") as f:
        yaml.dump({
            "id": task.id,
            "description": task.description,
            "context": task.context,
            "conventions": task.conventions,
            "dependencies": task.dependencies,
            "level": task.level,
            "assigned_model": task.assigned_model,
        }, f, default_flow_style=False)

    result_path = os.path.join(output_dir, f"{task.id}_result.md")
    result = {
        "task_id": task.id,
        "task_file": task_file,
        "result_path": result_path,
        "status": "pending",
        "error": None,
    }

    last_error = None
    model_spec = task.assigned_model
    for attempt in range(max_retries):
        try:
            prompt = build_executor_prompt(task, manifest)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as pf:
                pf.write(prompt)
                prompt_file = pf.name

            model = to_opencode_model(model_spec)
            proc = subprocess.run(
                ["opencode", "run", "--model", model, "Complete the attached task.", "--file", prompt_file],
                capture_output=True,
                text=True,
                timeout=300,
            )
            try:
                os.unlink(prompt_file)
            except OSError:
                pass

            if proc.returncode == 0 and proc.stdout.strip():
                result["status"] = "completed"
                with open(result_path, "w") as f:
                    f.write(proc.stdout)
                if task.output_file:
                    from src.manifest import ensure_manifest_header
                    ensure_manifest_header(task.output_file, task.output_file, task.description)
                return result
            elif proc.returncode == 0:
                last_error = "opencode returned empty output"
            else:
                stderr = proc.stderr.strip() or "opencode failed"
                last_error = stderr

            if router and router.is_rate_limit(last_error):
                router.register_failure(model_spec)
                fallback = router.next_fallback(model_spec)
                if fallback:
                    model_spec = fallback
                    last_error = None
                    continue
        except subprocess.TimeoutExpired:
            last_error = "task timed out (300s)"
        except FileNotFoundError:
            last_error = "opencode command not found"
        except Exception as e:
            last_error = str(e)

    result["status"] = "failed"
    result["error"] = f"Task failed after {max_retries} retries: {last_error}"
    return result


def execute_wave_v2(
    wave: Wave,
    output_dir: str,
    manifest: Dict = None,
    checkpointer: Checkpointer = None,
    router: ZenRouter = None,
) -> Wave:
    wave.status = "running"
    results = []

    if checkpointer:
        checkpointer.save_wave_state(wave)

    with ThreadPoolExecutor(max_workers=len(wave.tasks)) as executor:
        future_to_task = {
            executor.submit(execute_task_v2, task, output_dir, manifest, 3, router): task
            for task in wave.tasks
        }
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                res = future.result()
                results.append(res)
                if checkpointer:
                    checkpointer.save_task_state(task.id, res["status"], res.get("error"))
            except Exception as e:
                results.append({
                    "task_id": task.id,
                    "status": "failed",
                    "error": str(e),
                })
                if checkpointer:
                    checkpointer.save_task_state(task.id, "failed", str(e))

    wave.status = "completed" if all(r["status"] == "completed" for r in results) else "failed"
    wave.task_results = results
    return wave