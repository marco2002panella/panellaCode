from src.decomposer import parse_tasks
from src.decomposer import decompose
from src.models import Task
import pytest
from unittest.mock import MagicMock


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


def test_parse_task_with_fenced_yaml():
    yaml_text = """```yaml
- id: task_001
  description: "Test task"
  context:
    project_root: "/app"
    output_file: "test.py"
    related_files: []
  conventions:
    framework: ""
    language: "Python"
    style: ""
    code_split: []
  dependencies: []
  level: 0
  assigned_model: "default"
```"""
    tasks = parse_tasks(yaml_text)
    assert len(tasks) == 1
    assert tasks[0].id == "task_001"


def test_parse_rejects_truncated_task():
    yaml_text = """
- id: task_003
  description: Implement Bellman-Ford. The function should accept
"""
    with pytest.raises(ValueError, match="output_file"):
        parse_tasks(yaml_text)


def test_parse_rejects_placeholder_description():
    yaml_text = """
- id: task_001
  description: "..."
  context:
    output_file: graph.py
"""
    with pytest.raises(ValueError, match="description"):
        parse_tasks(yaml_text)


def test_parse_strips_quotes_from_assigned_model_fallback():
    yaml_text = """
- id: task_001
  description: Build the graph generator
  context:
    output_file: graph.py
  assigned_model: "default"
"""
    tasks = parse_tasks(yaml_text)
    assert tasks[0].assigned_model == "default"


def test_decompose_repairs_invalid_plan_with_fallback_model():
    valid_yaml = """
- id: task_001
  description: Build the graph generator
  context:
    project_root: /app
    output_file: graph.py
    related_files: []
  conventions:
    framework: none
    language: Python
    style: typed
    code_split: []
  dependencies: []
  level: 0
  assigned_model: default
"""
    client = MagicMock()
    client.chat.side_effect = ['- id: task_001\n  description: "..."', valid_yaml]

    tasks = decompose(
        "Build a graph generator",
        client,
        "regolo:qwen3.6-27b",
        repair_model_spec="regolo:qwen3-coder-next",
    )

    assert [task.id for task in tasks] == ["task_001"]
    assert client.chat.call_count == 2
    assert client.chat.call_args_list[1].args[0] == "regolo:qwen3-coder-next"
