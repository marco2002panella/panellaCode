import re
from typing import Any, Dict, List

import yaml

from src.api_client import APIClient
from src.config import load_template
from src.models import Task, TaskTemplate


def build_decomposer_prompt(
    problem: str,
    template: TaskTemplate,
    repository_context: str = None,
) -> str:
    instructions = template.decomposer_instructions.strip()
    prompt = f"{instructions}\n\nProblem to decompose:\n{problem}"
    if repository_context:
        prompt += f"\n\nRepository manifest:\n{repository_context}"
    return prompt


def _parse_yaml_safe(text: str) -> List[Task]:
    """Try standard YAML parsing."""
    try:
        raw_tasks = yaml.safe_load(text)
        if not isinstance(raw_tasks, list) or not raw_tasks:
            return None
        if "id" not in raw_tasks[0]:
            return None
        tasks = []
        for raw in raw_tasks:
            ctx = raw.get("context", {}) or {}
            conv = raw.get("conventions", {}) or {}
            tasks.append(Task(
                id=raw["id"],
                description=raw["description"],
                context=ctx if isinstance(ctx, dict) else {},
                conventions=conv if isinstance(conv, dict) else {},
                dependencies=raw.get("dependencies", []),
                level=raw.get("level", 0),
                assigned_model=raw.get("assigned_model", "default"),
            ))
        return tasks
    except yaml.YAMLError:
        return None


def _validate_tasks(tasks: List[Task]) -> List[Task]:
    for task in tasks:
        if not task.description.strip():
            raise ValueError(f"Task {task.id} has an empty description")
        if task.description.strip(" \t\"'") == "...":
            raise ValueError(f"Task {task.id} has a placeholder description")
        if not task.output_file:
            raise ValueError(f"Task {task.id} is missing context.output_file")
    return tasks


def _extract_inline_list(text: str) -> List[str]:
    """Parse inline list like [task_001, task_002]."""
    match = re.search(r"\[(.*?)\]", text)
    if match:
        return [x.strip().strip("'\"") for x in match.group(1).split(",") if x.strip()]
    return []


def _extract_multiline_list(text: str, start_line: int, prefix: str) -> List[str]:
    """Extract multi-line list items starting from a given line."""
    lines = text.split("\n")
    result = []
    for i in range(start_line, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("- "):
            result.append(stripped[2:].strip())
        elif stripped.startswith(f"{prefix}-"):
            result.append(stripped[len(prefix):].strip())
        elif not stripped or stripped.startswith(prefix):
            continue
        else:
            break
    return result


def _extract_tasks_regex(text: str) -> List[Task]:
    """Fallback: extract tasks by splitting on '- id:' markers."""
    split_points = [m.start() for m in re.finditer(r"^\s*- id:\s*", text, re.MULTILINE)]
    tasks = []

    for idx, start in enumerate(split_points):
        end = split_points[idx + 1] if idx + 1 < len(split_points) else len(text)
        block = text[start:end].strip()

        # Extract id
        id_match = re.search(r"- id:\s*(\S+)", block)
        if not id_match:
            continue
        task_id = id_match.group(1)

        # Extract description - can be multi-line, ends at next known key
        desc_match = re.search(r"description:\s*(.+?)(?=\n\s*(context|conventions|dependencies|level|assigned_model)|\Z)", block, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""
        # If description spans multiple lines, join them
        if "\n" in description:
            description = " ".join(description.split())

        # Extract context fields
        ctx = {}
        pr_match = re.search(r"project_root:\s*(.+)", block)
        of_match = re.search(r"output_file:\s*(.+)", block)
        rf_match = re.search(r"related_files:\s*\[(.*?)\]", block, re.DOTALL)
        if pr_match:
            ctx["project_root"] = pr_match.group(1).strip()
        if of_match:
            ctx["output_file"] = of_match.group(1).strip()
        if rf_match:
            ctx["related_files"] = [x.strip().strip("'\"") for x in rf_match.group(1).split(",") if x.strip()]
        else:
            ctx["related_files"] = []

        # Extract conventions fields
        conv = {}
        fw_match = re.search(r"framework:\s*(.+)", block)
        lang_match = re.search(r"language:\s*(.+)", block)
        style_match = re.search(r"style:\s*(.+)", block)
        cs_match = re.search(r"code_split:\s*\[(.*?)\]", block, re.DOTALL)
        if fw_match:
            conv["framework"] = fw_match.group(1).strip()
        if lang_match:
            conv["language"] = lang_match.group(1).strip()
        if style_match:
            conv["style"] = style_match.group(1).strip()
        if cs_match:
            conv["code_split"] = [x.strip().strip("'\"") for x in cs_match.group(1).split(",") if x.strip()]
        else:
            conv["code_split"] = []

        # Extract dependencies — inline [a, b] or multi-line - a\n- b
        dep_inline = re.search(r"dependencies:\s*\[(.*?)\]", block)
        if dep_inline:
            dependencies = [x.strip().strip("'\"") for x in dep_inline.group(1).split(",") if x.strip()]
        else:
            dep_match = re.search(r"dependencies:\s*\n((?:\s*-\s*\S+\s*\n?)*)", block)
            if dep_match:
                dependencies = [x.strip().lstrip("- ").strip() for x in dep_match.group(1).strip().split("\n") if x.strip()]
            else:
                dependencies = []

        # Extract level
        level_match = re.search(r"level:\s*(\d+)", block)
        level = int(level_match.group(1)) if level_match else 0

        # Extract assigned_model
        model_match = re.search(r"assigned_model:\s*(\S+)", block)
        assigned_model = model_match.group(1).strip("\"'") if model_match else "default"

        tasks.append(Task(
            id=task_id,
            description=description,
            context=ctx,
            conventions=conv,
            dependencies=dependencies,
            level=level,
            assigned_model=assigned_model,
        ))

    return tasks


def parse_tasks(yaml_text: str) -> List[Task]:
    cleaned = yaml_text.strip()

    # Try to extract from code blocks first
    match = re.search(r"```(?:yaml)?\s*\n(.*?)```", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()

    # Try standard YAML parse
    result = _parse_yaml_safe(cleaned)
    if result:
        return _validate_tasks(result)

    # Fallback: regex-based extraction
    return _validate_tasks(_extract_tasks_regex(cleaned))


def decompose(
    problem: str,
    client: APIClient,
    model_spec: str,
    repair_model_spec: str = None,
    repository_context: str = None,
) -> List[Task]:
    template = load_template()
    prompt = build_decomposer_prompt(problem, template, repository_context)
    messages = [
        {"role": "system", "content": "You are a task decomposition expert. Output valid YAML only."},
        {"role": "user", "content": prompt},
    ]
    response = client.chat(model_spec, messages)
    try:
        return parse_tasks(response)
    except ValueError as initial_error:
        if not repair_model_spec or repair_model_spec == model_spec:
            raise

        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You repair task plans. Return only a valid YAML list. "
                    "Every task must include id, description, context.output_file, "
                    "context.project_root, context.related_files, conventions, "
                    "dependencies, level, and assigned_model."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Repair the following invalid task plan. Preserve its intent, "
                    "complete missing fields, and do not add explanations.\n\n"
                    f"{response}"
                ),
            },
        ]
        repaired_response = client.chat(repair_model_spec, repair_messages)
        try:
            return parse_tasks(repaired_response)
        except ValueError as repair_error:
            raise ValueError(
                f"Task plan invalid after repair: {repair_error}"
            ) from initial_error
