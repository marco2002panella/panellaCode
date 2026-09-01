# Personal Agent — Parallel Task Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that decomposes a problem into subtasks, orders them into parallel waves, and dispatches each to an opencode instance.

**Architecture:** 4-phase pipeline (decompose → schedule → execute → collect) orchestrated sequentially, with parallel execution per wave via subprocess management.

**Tech Stack:** Python 3.12+, Typer, Pydantic, Rich, httpx, PyYAML

**Spec:** `docs/superpowers/specs/2026-08-28-personal-agent-design.md`

## Global Constraints

- Python 3.12+
- Dependencies: `typer`, `pydantic`, `rich`, `httpx`, `pyyaml`
- Config files in `config/`, output in `output/` (gitignored)
- Task YAML must include: id, description, context, conventions, dependencies, level, assigned_model
- API calls must support OpenAI-compatible format (shared by OpenRouter, Regolo, OpenCode Zen)
- Topological sort must detect cycles and report them

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `main.py`

**Interfaces:**
- Produces: project structure ready for imports

- [ ] **Step 1: Create requirements.txt**

```txt
typer>=0.12.0
pydantic>=2.0
rich>=13.0
httpx>=0.27.0
pyyaml>=6.0
```

- [ ] **Step 2: Create .gitignore**

```gitignore
output/
__pycache__/
*.pyc
.env
*.egg-info/
.venv/
```

- [ ] **Step 3: Create src/__init__.py and tests/__init__.py**

Empty files.

- [ ] **Step 4: Create main.py**

```python
#!/usr/bin/env python3
import typer

app = typer.Typer(name="myagent", help="Personal parallel task orchestrator")


def main():
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Verify structure**

Run: `python main.py --help`
Expected: Typer help output

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore src/__init__.py tests/__init__.py main.py
git commit -m "feat: project scaffolding"
```

---

### Task 2: Pydantic Data Models

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: none
- Produces: `Task`, `Wave`, `ProviderConfig`, `TaskTemplate`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from src.models import Task, Wave


def test_task_creation():
    task = Task(
        id="task_001",
        description="Implement auth endpoint",
        context={
            "project_root": "/app",
            "output_file": "src/auth.py",
            "related_files": ["src/db.py"],
        },
        conventions={
            "framework": "FastAPI",
            "language": "Python 3.12",
            "style": "type-hinted",
            "code_split": ["separate handlers"],
        },
        dependencies=[],
        level=0,
        assigned_model="openai:gpt-4o-mini",
    )
    assert task.id == "task_001"
    assert task.level == 0
    assert task.output_file == "src/auth.py"


def test_wave_creation():
    tasks = [
        Task(
            id="t1",
            description="A",
            context={"project_root": "/x", "output_file": "a.py", "related_files": []},
            conventions={"framework": "", "language": "", "style": "", "code_split": []},
            dependencies=[],
            level=0,
            assigned_model="openai:gpt-4o-mini",
        )
    ]
    wave = Wave(level=0, tasks=tasks, status="pending")
    assert wave.level == 0
    assert wave.status == "pending"
    assert len(wave.tasks) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'Task'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/models.py
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Task(BaseModel):
    id: str
    description: str
    context: dict = Field(default_factory=dict)
    conventions: dict = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    level: int = 0
    assigned_model: str = "openai:gpt-4o-mini"

    @property
    def output_file(self) -> Optional[str]:
        return self.context.get("output_file")

    @property
    def related_files(self) -> List[str]:
        return self.context.get("related_files", [])


class Wave(BaseModel):
    level: int
    tasks: List[Task] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed"] = "pending"


class ProviderConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    timeout: int = 60
    retry_count: int = 3


class TaskTemplate(BaseModel):
    fields: List[str] = Field(default_factory=list)
    decomposer_instructions: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: pydantic data models (Task, Wave, ProviderConfig, TaskTemplate)"
```

---

### Task 3: Config Loading

**Files:**
- Create: `config/default.yaml`
- Create: `config/template.yaml`
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: `ProviderConfig`, `TaskTemplate` from `models.py`
- Produces: `load_config(path) -> dict`, `load_template(path) -> TaskTemplate`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from src.config import load_config, load_template
import yaml


def test_load_default_config():
    cfg = load_config("config/default.yaml")
    assert "providers" in cfg
    assert "openai" in cfg["providers"]
    assert "models" in cfg


def test_load_template():
    template = load_template("config/template.yaml")
    assert isinstance(template.fields, list)
    assert len(template.decomposer_instructions) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write config/default.yaml**

```yaml
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    timeout: 60
    retry_count: 3
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
    timeout: 60
    retry_count: 3
  regolo:
    api_key: "${REGOLO_API_KEY}"
    base_url: ""
    timeout: 60
    retry_count: 3
  opencode_zen:
    api_key: "${OPENCODE_ZEN_API_KEY}"
    base_url: ""
    timeout: 60
    retry_count: 3

models:
  decomposer: "openai:gpt-4o-mini"
  scheduler: "openai:gpt-4o-mini"
  executor_default: "openai:gpt-4o-mini"
```

- [ ] **Step 4: Write config/template.yaml**

```yaml
fields:
  - id
  - description
  - context:
      - project_root
      - output_file
      - related_files
  - conventions:
      - framework
      - language
      - style
      - code_split
  - dependencies
  - level
  - assigned_model
decomposer_instructions: |
  You are a task decomposition expert. Break the given problem into the smallest
  independent subtasks possible. Each subtask must be self-contained so that an
  AI model can execute it without asking questions.

  For each subtask, output a YAML object with these fields:
  - id: unique identifier (task_001, task_002, ...)
  - description: clear, detailed description in English of what to do
  - context:
      project_root: the root directory of the project
      output_file: exact file path where the model should write results
      related_files: list of files to read for context (read-only)
  - conventions:
      framework: framework to use (e.g., FastAPI, React, Express)
      language: programming language and version
      style: coding style rules (e.g., type-hinted, SOLID)
      code_split: list of instructions on how to structure or split the code
  - dependencies: list of task IDs that must complete first (empty if none)
  - level: execution level (0 for no dependencies, assigned later by scheduler)
  - assigned_model: leave as "default" (scheduler will assign)

  Rules:
  - Make each task small enough to fit in a single context window
  - Include all file paths the model needs to know
  - Write descriptions in English
  - Only output valid YAML, no markdown formatting

  Output a YAML list of tasks.
```

- [ ] **Step 5: Write src/config.py**

```python
# src/config.py
import os
from typing import Any, Dict
import yaml
from src.models import TaskTemplate


def _expand_env_vars(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
    return value


def _expand_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _expand_dict(v)
        else:
            result[k] = _expand_env_vars(v)
    return result


def load_config(path: str = "config/default.yaml") -> Dict[str, Any]:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return _expand_dict(raw)


def load_template(path: str = "config/template.yaml") -> TaskTemplate:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return TaskTemplate(**raw)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add config/default.yaml config/template.yaml src/config.py tests/test_config.py
git commit -m "feat: config loading with env var expansion"
```

---

### Task 4: API Client

**Files:**
- Create: `src/api_client.py`
- Create: `tests/test_api_client.py`

**Interfaces:**
- Consumes: `load_config` from `config.py`
- Produces: `APIClient.chat(model_spec, messages) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_client.py
from src.api_client import APIClient


def test_resolve_provider():
    client = APIClient(config={
        "providers": {
            "openai": {"api_key": "sk-test", "base_url": "https://api.openai.com/v1"},
        },
    })
    provider, model = client._resolve("openai:gpt-4o-mini")
    assert provider["api_key"] == "sk-test"
    assert provider["base_url"] == "https://api.openai.com/v1"
    assert model == "gpt-4o-mini"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/api_client.py
import os
from typing import Any, Dict, List, Optional, Tuple
import httpx


class APIClient:
    def __init__(self, config: Dict[str, Any]):
        self.providers = config.get("providers", {})

    def _resolve(self, model_spec: str) -> Tuple[Dict[str, Any], str]:
        provider_name, model_name = model_spec.split(":", 1)
        provider = self.providers.get(provider_name, {})
        api_key = provider.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")
        return {
            "api_key": api_key,
            "base_url": provider.get("base_url", ""),
            "timeout": provider.get("timeout", 60),
            "retry_count": provider.get("retry_count", 3),
        }, model_name

    def chat(self, model_spec: str, messages: List[Dict[str, str]]) -> str:
        provider, model_name = self._resolve(model_spec)
        url = f"{provider['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model_name,
            "messages": messages,
        }
        max_retries = provider.get("retry_count", 3)
        last_error = None
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=provider.get("timeout", 60)) as client:
                    resp = client.post(url, json=body, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"API call failed after {max_retries} retries: {last_error}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api_client.py tests/test_api_client.py
git commit -m "feat: API client with provider resolution and retry"
```

---

### Task 5: Decomposer

**Files:**
- Create: `src/decomposer.py`
- Create: `tests/test_decomposer.py`

**Interfaces:**
- Consumes: `APIClient` from `api_client.py`, `load_template` from `config.py`
- Produces: `decompose(problem, client, template, model_spec) -> List[Task]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_decomposer.py
from src.decomposer import parse_tasks
from src.models import Task


def test_parse_single_task():
    yaml_text = """
- id: task_001
  description: "Create database schema"
  context:
    project_root: "/app"
    output_file: "schema.sql"
    related_files: []
  conventions:
    framework: ""
    language: "SQL"
    style: "PostgreSQL"
    code_split: []
  dependencies: []
  level: 0
  assigned_model: "default"
"""
    tasks = parse_tasks(yaml_text)
    assert len(tasks) == 1
    assert tasks[0].id == "task_001"
    assert tasks[0].description == "Create database schema"


def test_parse_multiple_tasks_with_deps():
    yaml_text = """
- id: task_001
  description: "Setup project"
  context:
    project_root: "/app"
    output_file: "setup.py"
    related_files: []
  conventions:
    framework: ""
    language: "Python"
    style: ""
    code_split: []
  dependencies: []
  level: 0
  assigned_model: "default"
- id: task_002
  description: "Add auth"
  context:
    project_root: "/app"
    output_file: "auth.py"
    related_files: ["setup.py"]
  conventions:
    framework: "FastAPI"
    language: "Python"
    style: ""
    code_split: []
  dependencies: ["task_001"]
  level: 0
  assigned_model: "default"
"""
    tasks = parse_tasks(yaml_text)
    assert len(tasks) == 2
    assert tasks[1].dependencies == ["task_001"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_decomposer.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/decomposer.py
from typing import List
import yaml
from src.models import Task
from src.api_client import APIClient
from src.config import load_template


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_decomposer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/decomposer.py tests/test_decomposer.py
git commit -m "feat: task decomposer with YAML parsing"
```

---

### Task 6: Scheduler (Topological Sort)

**Files:**
- Create: `src/scheduler.py`
- Create: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `Task`, `Wave` from `models.py`
- Produces: `schedule(tasks) -> List[Wave]`, `topological_sort(tasks) -> List[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scheduler.py
from src.scheduler import topological_sort, schedule, CycleError
from src.models import Task


def _make_task(tid: str, deps: list = None) -> Task:
    return Task(
        id=tid,
        description=tid,
        context={"project_root": "/x", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=deps or [],
        level=0,
        assigned_model="default",
    )


def test_topo_linear():
    tasks = [
        _make_task("t1"),
        _make_task("t2", ["t1"]),
        _make_task("t3", ["t2"]),
    ]
    order = topological_sort(tasks)
    assert order.index("t1") < order.index("t2")
    assert order.index("t2") < order.index("t3")


def test_topo_parallel():
    tasks = [
        _make_task("t1"),
        _make_task("t2"),
        _make_task("t3", ["t1", "t2"]),
    ]
    waves = schedule(tasks)
    assert len(waves) == 2
    assert waves[0].level == 0
    assert {w.id for w in waves[0].tasks} == {"t1", "t2"}
    assert waves[1].level == 1
    assert {w.id for w in waves[1].tasks} == {"t3"}


def test_topo_diamond():
    tasks = [
        _make_task("t1"),
        _make_task("t2", ["t1"]),
        _make_task("t3", ["t1"]),
        _make_task("t4", ["t2", "t3"]),
    ]
    waves = schedule(tasks)
    assert len(waves) == 3
    assert {w.id for w in waves[0].tasks} == {"t1"}
    assert {w.id for w in waves[1].tasks} == {"t2", "t3"}
    assert {w.id for w in waves[2].tasks} == {"t4"}


def test_topo_cycle_raises():
    t1 = _make_task("t1", ["t2"])
    t2 = _make_task("t2", ["t1"])
    try:
        topological_sort([t1, t2])
        assert False, "Should have raised CycleError"
    except CycleError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/scheduler.py
from typing import Dict, List, Set
from collections import defaultdict, deque
from src.models import Task, Wave


class CycleError(Exception):
    pass


def topological_sort(tasks: List[Task]) -> List[str]:
    task_map = {t.id: t for t in tasks}
    in_degree: Dict[str, int] = {t.id: 0 for t in tasks}
    dependents: Dict[str, List[str]] = defaultdict(list)

    for t in tasks:
        for dep in t.dependencies:
            if dep not in task_map:
                continue
            dependents[dep].append(t.id)
            in_degree[t.id] += 1

    queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for dependent in dependents[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(tasks):
        remaining = set(t.id for t in tasks) - set(result)
        raise CycleError(f"Cycle detected among tasks: {remaining}")

    return result


def schedule(tasks: List[Task]) -> List[Wave]:
    if not tasks:
        return []

    task_map = {t.id: t for t in tasks}
    levels: Dict[str, int] = {}

    def get_level(tid: str) -> int:
        if tid in levels:
            return levels[tid]
        task = task_map[tid]
        if not task.dependencies:
            levels[tid] = 0
            return 0
        max_dep_level = max(get_level(dep) for dep in task.dependencies if dep in task_map)
        levels[tid] = max_dep_level + 1
        return levels[tid]

    for t in tasks:
        get_level(t.id)

    wave_map: Dict[int, List[Task]] = defaultdict(list)
    for t in tasks:
        t.level = levels[t.id]
        wave_map[levels[t.id]].append(t)

    waves = []
    for level in sorted(wave_map.keys()):
        waves.append(Wave(level=level, tasks=wave_map[level], status="pending"))

    return waves
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/scheduler.py tests/test_scheduler.py
git commit -m "feat: scheduler with topological sort and wave grouping"
```

---

### Task 7: Executor (Opencode Subprocesses)

**Files:**
- Create: `src/executor.py`
- Create: `tests/test_executor.py`

**Interfaces:**
- Consumes: `Task`, `Wave` from `models.py`
- Produces: `write_task_file(task, output_dir) -> str`, `execute_wave(wave, output_dir, model_map) -> Wave`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_executor.py
from src.executor import write_task_file
from src.models import Task
import yaml
import os


def test_write_task_file():
    task = Task(
        id="task_001",
        description="Test task",
        context={"project_root": "/app", "output_file": "out.py", "related_files": []},
        conventions={"framework": "", "language": "Python", "style": "", "code_split": []},
        dependencies=[],
        level=0,
        assigned_model="openai:gpt-4o-mini",
    )
    path = write_task_file(task, "/tmp/test_executor")
    assert os.path.exists(path)
    with open(path) as f:
        data = yaml.safe_load(f)
    assert data["id"] == "task_001"
    assert data["description"] == "Test task"
    import shutil
    shutil.rmtree("/tmp/test_executor", ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_executor.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/executor.py
import os
import subprocess
import time
import yaml
from pathlib import Path
from typing import Dict, List, Optional
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_executor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/executor.py tests/test_executor.py
git commit -m "feat: executor with opencode subprocess management"
```

---

### Task 8: Collector

**Files:**
- Create: `src/collector.py`
- Create: `tests/test_collector.py`

**Interfaces:**
- Consumes: `Wave` from `models.py`
- Produces: `collect_results(waves, output_dir) -> str`, `generate_report(waves) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_collector.py
from src.collector import generate_report
from src.models import Task, Wave


def _make_task(tid: str) -> Task:
    return Task(
        id=tid,
        description=f"Task {tid}",
        context={"project_root": "/x", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=[],
        level=0,
        assigned_model="default",
    )


def test_generate_report():
    waves = [
        Wave(
            level=0,
            tasks=[_make_task("t1"), _make_task("t2")],
            status="completed",
        ),
        Wave(
            level=1,
            tasks=[_make_task("t3")],
            status="completed",
        ),
    ]
    report = generate_report(waves)
    assert "Wave 0" in report
    assert "Wave 1" in report
    assert "t1" in report
    assert "t3" in report
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_collector.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/collector.py
import os
from typing import List
from src.models import Wave


def collect_results(waves: List[Wave], output_dir: str) -> List[str]:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_collector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/collector.py tests/test_collector.py
git commit -m "feat: collector with result aggregation and report generation"
```

---

### Task 9: Orchestrator

**Files:**
- Create: `src/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: all modules
- Produces: `run(problem, config_path, output_dir, model_map) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestrator.py
from src.orchestrator import Orchestrator


def test_orchestrator_init():
    orch = Orchestrator(config={"providers": {}, "models": {"decomposer": "openai:gpt-4o-mini"}})
    assert orch is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/orchestrator.py
from typing import Dict, List, Optional, Any
from src.config import load_config
from src.api_client import APIClient
from src.decomposer import decompose
from src.scheduler import schedule
from src.executor import execute_wave
from src.collector import generate_report, save_report, collect_results
from src.models import Wave


class Orchestrator:
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: str = "config/default.yaml"):
        self.config = config or load_config(config_path)
        self.client = APIClient(self.config)
        self.model_config = self.config.get("models", {})

    def run(
        self,
        problem: str,
        output_dir: str = "output",
        model_map: Optional[Dict[str, str]] = None,
    ) -> str:
        decomposer_model = model_map.get("decomposer", self.model_config.get("decomposer", "openai:gpt-4o-mini"))
        executor_model = model_map.get("executor_default", self.model_config.get("executor_default", "openai:gpt-4o-mini"))

        # Phase 1: Decompose
        print("[1/4] Decomposing problem...")
        tasks = decompose(problem, self.client, decomposer_model)
        print(f"      Found {len(tasks)} subtasks")

        # Override model assignment
        for task in tasks:
            if task.assigned_model == "default":
                task.assigned_model = executor_model

        # Phase 2: Schedule
        print("[2/4] Scheduling tasks...")
        waves = schedule(tasks)
        for w in waves:
            print(f"      Wave {w.level}: {len(w.tasks)} tasks (parallel)")

        # Phase 3: Execute
        print("[3/4] Executing waves...")
        import os
        task_dir = os.path.join(output_dir, "tasks")
        result_dir = os.path.join(output_dir, "results")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)

        for wave in waves:
            print(f"\n  >>> Wave {wave.level} ({wave.status})")
            execute_wave(wave, task_dir)

        # Phase 4: Collect
        print("\n[4/4] Collecting results...")
        report = generate_report(waves)
        report_path = save_report(report, result_dir)
        print(f"      Report saved to {report_path}")

        return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator coordinating all 4 phases"
```

---

### Task 10: CLI Interface

**Files:**
- Modify: `src/cli.py` (create)
- Modify: `main.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Orchestrator` from `orchestrator.py`
- Produces: CLI commands via Typer

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from typer.testing import CliRunner
from src.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output


def test_cli_run_requires_problem():
    result = runner.invoke(app, ["run"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write src/cli.py**

```python
# src/cli.py
import typer
from typing import Optional
from src.orchestrator import Orchestrator

app = typer.Typer()


@app.command()
def run(
    problem: str = typer.Argument(..., help="The problem to solve"),
    config: str = typer.Option("config/default.yaml", "--config", "-c", help="Config file path"),
    output: str = typer.Option("output", "--output", "-o", help="Output directory"),
    decomposer_model: Optional[str] = typer.Option(None, "--decomposer-model", help="Model for decomposition"),
    executor_model: Optional[str] = typer.Option(None, "--executor-model", help="Default model for execution"),
):
    model_map = {}
    if decomposer_model:
        model_map["decomposer"] = decomposer_model
    if executor_model:
        model_map["executor_default"] = executor_model

    orch = Orchestrator(config_path=config)
    report = orch.run(problem, output_dir=output, model_map=model_map if model_map else None)
    typer.echo("\n" + report)


@app.command()
def version():
    typer.echo("myagent 0.1.0")
```

- [ ] **Step 4: Update main.py**

```python
#!/usr/bin/env python3
from src.cli import app


def main():
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/cli.py main.py tests/test_cli.py
git commit -m "feat: CLI interface with run and version commands"
```

---

### Task 11: TUI Monitoring with Rich

**Files:**
- Modify: `src/executor.py`
- Create: `src/monitor.py`
- Create: `tests/test_monitor.py`

**Interfaces:**
- Consumes: `Wave` from `models.py`
- Produces: `Monitor` class for live TUI updates

- [ ] **Step 1: Write the failing test**

```python
# tests/test_monitor.py
from src.monitor import Monitor
from src.models import Task, Wave


def _make_task(tid: str) -> Task:
    return Task(
        id=tid,
        description=f"Task {tid}",
        context={"project_root": "/x", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=[],
        level=0,
        assigned_model="default",
    )


def test_monitor_init():
    waves = [Wave(level=0, tasks=[_make_task("t1"), _make_task("t2")], status="pending")]
    monitor = Monitor(waves)
    assert len(monitor.waves) == 1


def test_monitor_update_task():
    waves = [Wave(level=0, tasks=[_make_task("t1")], status="pending")]
    monitor = Monitor(waves)
    monitor.update_task("t1", "running")
    assert monitor.waves[0].tasks[0].status == "running"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/monitor.py
from typing import Dict, List, Optional
from src.models import Task, Wave


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MonitoredTask(Task):
    status: str = "pending"


class Monitor:
    def __init__(self, waves: List[Wave]):
        self.waves = waves
        self._task_map: Dict[str, MonitoredTask] = {}
        for wave in waves:
            for task in wave.tasks:
                mt = MonitoredTask(**task.model_dump())
                self._task_map[task.id] = mt

    def update_task(self, task_id: str, status: str):
        if task_id in self._task_map:
            self._task_map[task_id].status = status

    def get_task_status(self, task_id: str) -> Optional[str]:
        return self._task_map.get(task_id).status if task_id in self._task_map else None

    @property
    def total_tasks(self) -> int:
        return len(self._task_map)

    @property
    def completed_tasks(self) -> int:
        return sum(1 for t in self._task_map.values() if t.status == "completed")

    @property
    def failed_tasks(self) -> int:
        return sum(1 for t in self._task_map.values() if t.status == "failed")

    def render(self) -> str:
        lines = []
        for wave in self.waves:
            wave_tasks = [self._task_map[t.id] for t in wave.tasks if t.id in self._task_map]
            status_icons = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
            }
            lines.append(f"\n[bold]Wave {wave.level}[/bold] [{wave.status}]:")
            for t in wave_tasks:
                icon = status_icons.get(t.status, "?")
                lines.append(f"  {icon} {t.id}: {t.description[:50]}")
        lines.append(f"\nProgress: {self.completed_tasks}/{self.total_tasks} completed, {self.failed_tasks} failed")
        return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/monitor.py tests/test_monitor.py
git commit -m "feat: TUI monitor for task tracking"
```

---

### Task 12: Integration Test (Mock API)

**Files:**
- Create: `tests/test_integration.py`

**Interfaces:**
- Consumes: all modules
- Produces: end-to-end test with mocked API

- [ ] **Step 1: Write the integration test**

```python
# tests/test_integration.py
from src.scheduler import schedule
from src.collector import generate_report
from src.models import Task


def _make_task(tid: str, deps: list = None) -> Task:
    return Task(
        id=tid,
        description=f"Description for {tid}",
        context={"project_root": "/app", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "FastAPI", "language": "Python 3.12", "style": "", "code_split": []},
        dependencies=deps or [],
        level=0,
        assigned_model="openai:gpt-4o-mini",
    )


def test_full_pipeline_schedule_and_collect():
    tasks = [
        _make_task("t1"),
        _make_task("t2"),
        _make_task("t3", ["t1"]),
        _make_task("t4", ["t1", "t2"]),
        _make_task("t5", ["t3", "t4"]),
    ]
    waves = schedule(tasks)
    assert len(waves) == 3

    for wave in waves:
        for task in wave.tasks:
            if not hasattr(wave, "task_results"):
                wave.task_results = []
            wave.task_results.append({
                "task_id": task.id,
                "status": "completed",
                "error": None,
            })

    report = generate_report(waves)
    assert "Wave 0" in report
    assert "Wave 1" in report
    assert "Wave 2" in report
    assert "Completed: 5" in report
    assert "Failed: 0" in report
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "feat: integration test for schedule+collect pipeline"
```

---

### Task 13: Parallel Wave Execution

**Files:**
- Modify: `src/executor.py`

**Interfaces:**
- Consumes: `Task`, `Wave` from `models.py`
- Produces: parallel `execute_wave` using `concurrent.futures`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_executor_parallel.py
from src.executor import execute_wave_parallel
from src.models import Task, Wave
import time


def _make_task(tid: str) -> Task:
    return Task(
        id=tid,
        description=f"Task {tid}",
        context={"project_root": "/x", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=[],
        level=0,
        assigned_model="default",
    )


def test_parallel_execution_is_faster():
    wave = Wave(level=0, tasks=[_make_task("t1"), _make_task("t2"), _make_task("t3")], status="pending")
    start = time.time()
    result_wave = execute_wave_parallel(wave, "/tmp/test_parallel")
    elapsed = time.time() - start
    assert elapsed < 2, "Parallel execution should finish in under 2s"
    import shutil
    shutil.rmtree("/tmp/test_parallel", ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_executor_parallel.py -v`
Expected: FAIL — `ImportError` for `execute_wave_parallel`

- [ ] **Step 3: Add parallel execution to executor.py**

Add to `src/executor.py`:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed


def execute_wave_parallel(wave: Wave, output_dir: str) -> Wave:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_executor_parallel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/executor.py tests/test_executor_parallel.py
git commit -m "feat: parallel wave execution with ThreadPoolExecutor"
```

---

### Task 14: Wire TUI Into Orchestrator

**Files:**
- Modify: `src/orchestrator.py`
- Modify: `src/executor.py`

**Interfaces:**
- Consumes: `Monitor` from `monitor.py`
- Produces: live TUI updates during execution

- [ ] **Step 1: Update orchestrator.py to use Monitor**

In `src/orchestrator.py`, add to `run()`:

```python
from src.monitor import Monitor

# ... inside run(), after scheduling:

        monitor = Monitor(waves)

        # Phase 3: Execute
        print("[3/4] Executing waves...")
        from src.executor import execute_wave_parallel

        for wave in waves:
            print(f"\n  >>> Wave {wave.level}")
            for task in wave.tasks:
                monitor.update_task(task.id, "running")
            execute_wave_parallel(wave, task_dir)
            for res in wave.task_results:
                monitor.update_task(res["task_id"], res["status"])

            print(monitor.render())
```

- [ ] **Step 2: Verify full run**

Run: `python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add src/orchestrator.py src/executor.py
git commit -m "feat: wire TUI monitor into orchestrator"
```

---

### Task 15: Final Polish

**Files:**
- Modify: `main.py` (make executable)
- Add: `pytest.ini`

- [ ] **Step 1: Create pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 2: Make main.py executable**

```bash
chmod +x main.py
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add pytest.ini main.py
git commit -m "polish: pytest config and executable entry point"
```

---

## Self-Review Checklist

- **Spec coverage:** All 4 phases covered (decompose T5, schedule T6, execute T7+T13, collect T8). Config T3, API T4, orchestrator T9, CLI T10, TUI T11+T14, integration T12. ✅
- **Placeholder scan:** No TBDs, no "implement later". Every step has actual code. ✅
- **Type consistency:** `Task`, `Wave`, `Wave.task_results` used consistently. `MonitoredTask` extends `Task` with `status`. ✅
- **Dependency order:** Models → Config → API → Decomposer → Scheduler → Executor → Collector → Orchestrator → CLI → Monitor → Integration → Parallel → Wire. ✅