# Personal Agent — Parallel Task Orchestrator

## Overview

A CLI application that decomposes a user's problem into smaller subtasks, orders them into parallel execution levels via topological sort, and dispatches each subtask to an opencode instance running with a selected model. Results are collected and aggregated into a final report.

**Goal:** Increase throughput by parallelizing work across multiple model instances, and leverage free/cheap models for decomposed subtasks.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   User CLI  │────>│ Orchestrator │────>│ Decomposer  │──> API (model A)
└─────────────┘     └──────────────┘     └─────────────┘
                                │
                                ├──> Scheduler ──> topological levels
                                │
                                ├──> Executor ──> spawn opencode instances (parallel per level)
                                │
                                └──> Collector ──> aggregate results, final report
```

### Components

| Module | Responsibility |
|--------|----------------|
| `main.py` | Entry point |
| `cli.py` | Argument parsing (typer): problem input, model config, output path |
| `orchestrator.py` | Coordinates the 4 phases sequentially |
| `api_client.py` | HTTP calls to providers (OpenAI, OpenRouter, Regolo AI, OpenCode Zen) |
| `decomposer.py` | Sends problem + template to model API → receives list of YAML subtasks |
| `scheduler.py` | Computes topological ordering, groups tasks into parallel waves |
| `executor.py` | For each task: writes YAML file, spawns opencode subprocess, tracks state |
| `collector.py` | Reads output files from opencode instances, generates final report |
| `models.py` | Pydantic data models for tasks, waves, results |

## Configuration

### `config/default.yaml`

Provider API keys and model mapping:

```yaml
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    base_url: "https://openrouter.ai/api/v1"
  regolo:
    api_key: "${REGOLO_API_KEY}"
    base_url: "..."
  opencode_zen:
    api_key: "${OPENCODE_ZEN_API_KEY}"
    base_url: "..."

models:
  decomposer: "openai:gpt-4o-mini"
  scheduler: "openai:gpt-4o-mini"
  executor_default: "openrouter:..."
```

### `config/template.yaml`

The task template — defines the structure and instructions every subtask must follow. This is what the decomposer uses as context when breaking down problems.

```yaml
task_schema:
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
  Break the given problem into the smallest independent subtasks possible.
  For each subtask, fill in all fields of the task_schema above.
  - description: what the model must do, written clearly in English
  - context.output_file: the exact file path where the model should write its result
  - context.related_files: files the model should read for context
  - conventions.framework: which framework to use
  - conventions.language: programming language and version
  - conventions.style: coding style rules
  - conventions.code_split: how to structure or split the code
  - dependencies: list of task IDs that must complete first
  Output valid YAML only.
```

## Data Models

### Task (subtask YAML)

```yaml
id: task_001
description: >
  Implement the user authentication endpoint using FastAPI.
context:
  project_root: "/home/user/myapp"
  output_file: "src/auth/endpoint.py"
  related_files:
    - "src/models/user.py"
    - "src/config/settings.py"
conventions:
  framework: "FastAPI"
  language: "Python 3.12"
  style: "type-hinted, pydantic models"
  code_split:
    - "Separate route handlers from business logic"
    - "One function per responsibility"
dependencies: []
level: 0
assigned_model: "openai:gpt-4o-mini"
```

### Wave (execution level)

```python
Wave(
  level: int,
  tasks: List[Task],
  status: "pending" | "running" | "completed" | "failed"
)
```

## Execution Flow

1. **Decompose** — CLI receives user problem → decomposer sends it to the configured model with the template → receives list of Task YAML
2. **Schedule** — scheduler reads task dependencies → topological sort → groups into waves by level
3. **Execute** — executor processes waves sequentially:
   - For each wave, spawn all tasks in parallel
   - Each task: write YAML to `output/tasks/<id>.yaml`, launch opencode subprocess
   - Wait for all tasks in wave to complete before next wave
4. **Collect** — collector reads each task's output file → generates consolidated report

## Monitoring

TUI built with `rich` showing:
- Current wave and progress
- Per-task status (pending, running, done, failed)
- Log output from each opencode instance (toggleable)

## Technology Choices

- **Language:** Python 3.12+
- **CLI framework:** Typer
- **Data validation:** Pydantic
- **TUI:** Rich
- **Config:** YAML (PyYAML)
- **API calls:** `httpx` (async)

## File Structure

```
myagent/
├── main.py
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── orchestrator.py
│   ├── api_client.py
│   ├── decomposer.py
│   ├── scheduler.py
│   ├── executor.py
│   ├── collector.py
│   └── models.py
├── config/
│   ├── default.yaml
│   └── template.yaml
├── output/                      # gitignored
│   ├── tasks/                   # task YAML files
│   │   └── task_001.yaml
│   └── results/                 # opencode output files
│       └── task_001_result.md
├── requirements.txt
└── .gitignore
```

## Provider API Handling

The `api_client.py` module abstracts provider differences:
- Resolves `"provider:model"` strings to correct base URL + headers
- Falls back to OpenAI-compatible format (most providers support it)
- Configurable timeout, retry count per provider

## Error Handling

- **API failure:** retry up to 3 times, then mark task as failed and continue
- **Opencode failure:** capture exit code + stderr, mark task failed, continue wave
- **Partial failure:** collector reports which tasks succeeded/failed, doesn't block other waves

## Testing Strategy

- Unit tests for scheduler (topological sort with cycles, diamonds, single chain)
- Unit tests for decomposer output parsing (YAML validation)
- Integration test: mock API → decompose → schedule → verify waves