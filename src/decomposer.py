from typing import List

import yaml

from src.api_client import APIClient
from src.config import load_template
from src.models import Task, TaskTemplate


def build_decomposer_prompt(problem: str, template: TaskTemplate) -> str:
    instructions = template.decomposer_instructions.strip()
    return f"{instructions}\n\nProblem to decompose:\n{problem}"


def parse_tasks(yaml_text: str) -> List[Task]:
    cleaned = yaml_text.strip()
    if cleaned.startswith("```yaml"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    raw_tasks = yaml.safe_load(cleaned)
    if not isinstance(raw_tasks, list):
        raw_tasks = [raw_tasks]
    tasks = []
    for raw in raw_tasks:
        ctx = raw.get("context", {})
        conv = raw.get("conventions", {})
        if not isinstance(ctx, dict):
            ctx = {}
        if not isinstance(conv, dict):
            conv = {}
        tasks.append(Task(
            id=raw["id"],
            description=raw["description"],
            context=ctx,
            conventions=conv,
            dependencies=raw.get("dependencies", []),
            level=raw.get("level", 0),
            assigned_model=raw.get("assigned_model", "default"),
        ))
    return tasks


def decompose(problem: str, client: APIClient, model_spec: str) -> List[Task]:
    template = load_template()
    prompt = build_decomposer_prompt(problem, template)
    messages = [
        {"role": "system", "content": "You are a task decomposition expert. Output valid YAML only."},
        {"role": "user", "content": prompt},
    ]
    response = client.chat(model_spec, messages)
    return parse_tasks(response)
