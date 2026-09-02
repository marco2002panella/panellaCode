# src/executor_stream.py
"""Streaming executor: runs `opencode run` with live stdout lines pushed
to a callback, instead of a blocking capture. Used by the TUI.

`run_executor(task, ..., mode="blocking"|"stream")` is the facade:
  - blocking: identical to executor_v2.execute_task_v2 (CLI `run`).
  - stream:   Popen + reader thread, lines pushed to on_output.
"""

import os
import subprocess
import tempfile
import threading
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional

from src.executor_v2 import build_executor_prompt, execute_task_v2
from src.checkpointing import Checkpointer
from src.models import Task, Wave
from src.zen_router import ZenRouter, to_opencode_model


def _stream_subprocess_lines(
    cmd: List[str],
    on_output: Optional[Callable[[str, bool], None]] = None,
    timeout: int = 300,
) -> int:
    """Run `cmd` via Popen, streaming stdout/stderr lines to on_output(line, is_stderr).
    Returns the process exit code. Raises subprocess.TimeoutExpired on timeout,
    returns 127 if the binary is missing.
    """
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        return 127

    def pump(pipe, is_stderr):
        try:
            for line in iter(pipe.readline, ""):
                if on_output:
                    on_output(line.rstrip("\n"), is_stderr)
        finally:
            pipe.close()

    threads = [
        threading.Thread(target=pump, args=(proc.stdout, False), daemon=True),
        threading.Thread(target=pump, args=(proc.stderr, True), daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    finally:
        for t in threads:
            t.join(timeout=5)


def _write_task_file(task: Task, output_dir: str) -> str:
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


def execute_task_v2_stream(
    task: Task,
    output_dir: str,
    manifest: Dict = None,
    max_retries: int = 3,
    router: ZenRouter = None,
    on_output: Optional[Callable[[str, bool], None]] = None,
    on_done: Optional[Callable[[Dict], None]] = None,
    proc_lock: threading.Lock = None,
) -> Dict:
    task_file = _write_task_file(task, output_dir)
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
            cmd = [
                "opencode", "run", "--model", model,
                "Complete the attached task.", "--file", prompt_file,
            ]

            lines: List[str] = []

            def _hook(line: str, is_stderr: bool):
                if not is_stderr and line.strip():
                    lines.append(line)
                if on_output:
                    on_output(line, is_stderr)

            if proc_lock:
                proc_lock.acquire()
            try:
                rc = _stream_subprocess_lines(cmd, on_output=_hook, timeout=300)
            finally:
                if proc_lock:
                    proc_lock.release()

            try:
                os.unlink(prompt_file)
            except OSError:
                pass

            stdout = "".join(lines)
            if rc == 0 and stdout.strip():
                result["status"] = "completed"
                with open(result_path, "w") as f:
                    f.write(stdout)
                if task.output_file:
                    from src.manifest import ensure_manifest_header
                    ensure_manifest_header(task.output_file, task.output_file, task.description)
                if on_done:
                    on_done(dict(result))
                return result
            elif rc == 0:
                last_error = "opencode returned empty output"
            else:
                last_error = "opencode failed"

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
    if on_done:
        on_done(dict(result))
    return result


def execute_wave_v2_stream(
    wave: Wave,
    output_dir: str,
    manifest: Dict = None,
    checkpointer: Checkpointer = None,
    router: ZenRouter = None,
    on_output: Optional[Callable[[str, str, bool], None]] = None,
    on_done: Optional[Callable[[Dict], None]] = None,
    proc_lock: threading.Lock = None,
) -> Wave:
    """Like execute_wave_v2 but live-streaming.

    on_output(task_id, line, is_stderr) is called for every line with the
    owning task's id, so the TUI can tag log lines per task.
    """
    wave.status = "running"
    results = []

    if checkpointer:
        checkpointer.save_wave_state(wave)

    with ThreadPoolExecutor(max_workers=len(wave.tasks)) as executor:
        future_to_task = {
            executor.submit(
                execute_task_v2_stream,
                task, output_dir, manifest, 3, router,
                (on_output and (lambda line, is_stderr, _t=task.id: on_output(_t, line, is_stderr))),
                on_done, proc_lock,
            ): task
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
                if on_done:
                    on_done(results[-1])
                if checkpointer:
                    checkpointer.save_task_state(task.id, "failed", str(e))

    wave.status = "completed" if all(r["status"] == "completed" for r in results) else "failed"
    wave.task_results = results
    return wave


def run_executor(task: Task, output_dir: str, manifest: Dict = None, mode: str = "blocking", **kwargs) -> Dict:
    """Facade: mode='blocking' is identical to executor_v2.execute_task_v2;
    mode='stream' returns live stdout via on_output and on_done callbacks."""
    if mode == "stream":
        return execute_task_v2_stream(task, output_dir, manifest, **kwargs)
    return execute_task_v2(task, output_dir, manifest, **kwargs)