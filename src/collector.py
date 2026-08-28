import os
from typing import List
from src.models import Wave


def collect_results(waves: List[Wave], output_dir: str) -> list[dict]:
    results = []
    for wave in waves:
        if hasattr(wave, "task_results"):
            for res in wave.task_results:
                results.append(res)
    return results


def generate_report(waves: List[Wave]) -> str:
    lines = ["# Execution Report\n"]
    total_tasks = 0
    completed_tasks = 0

    for wave in waves:
        lines.append(f"\n## Wave {wave.level} ({wave.status})\n")
        for task in wave.tasks:
            total_tasks += 1
            lines.append(f"- **{task.id}**: {task.description}")
            lines.append(f"  - Model: {task.assigned_model}")
            lines.append(f"  - Output: {task.output_file}")
            if hasattr(wave, "task_results"):
                for res in wave.task_results:
                    if res["task_id"] == task.id:
                        status = res["status"]
                        if status == "completed":
                            completed_tasks += 1
                            lines.append(f"  - Status: COMPLETED")
                        else:
                            lines.append(f"  - Status: FAILED — {res.get('error', 'unknown')}")
                        break

    lines.append(f"\n## Summary\n")
    lines.append(f"- Total tasks: {total_tasks}")
    lines.append(f"- Completed: {completed_tasks}")
    lines.append(f"- Failed: {total_tasks - completed_tasks}")

    return "\n".join(lines)


def save_report(report: str, output_dir: str, filename: str = "report.md") -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        f.write(report)
    return path
