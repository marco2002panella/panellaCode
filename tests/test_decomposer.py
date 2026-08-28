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