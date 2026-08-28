# myagent

A personal AI agent that decomposes complex problems into parallelizable subtasks, executes them across multiple LLM providers, and collects structured results.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `config/default.yaml` and set your API keys as environment variables:

```bash
export OPENAI_API_KEY="sk-..."
# export OPENROUTER_API_KEY="sk-or-..."
# export REGOLO_API_KEY="sk-..."
# export OPENCODE_ZEN_API_KEY="sk-..."
```

The config file supports multiple providers (`openai`, `openrouter`, `regolo`, `opencode_zen`) and lets you assign models per role:

```yaml
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    timeout: 60
    retry_count: 3

models:
  decomposer: "openai:gpt-4o-mini"
  scheduler: "openai:gpt-4o-mini"
  executor_default: "openai:gpt-4o-mini"
```

## Usage

```bash
# Solve a problem
python main.py run "Build a REST API with FastAPI for a todo app"

# Custom config and output directory
python main.py run "Create a React dashboard" -c config/my.yaml -o my_output

# Override models
python main.py run "Write unit tests" --decomposer-model "openai:gpt-4o" --executor-model "openai:gpt-4o-mini"

# Check version
python main.py version
```

## Architecture

```
main.py (CLI entry)
  └── src/cli.py          Typer CLI: run and version commands
        └── src/orchestrator.py  4-phase orchestration
              ├── src/decomposer.py      Phase 1: break problem into tasks
              ├── src/scheduler.py       Phase 2: group tasks into parallel waves
              ├── src/executor.py        Phase 3: execute waves (parallel via ThreadPoolExecutor)
              └── src/collector.py       Phase 4: aggregate results into a report
              │
              ├── src/api_client.py      HTTP client with retry logic
              ├── src/config.py          YAML config loader with env var interpolation
              ├── src/monitor.py         TUI progress monitor
              └── src/models.py          Pydantic models: Task, Wave, ProviderConfig
```

### Execution Flow

1. **Decompose** – An LLM breaks the problem into small, independent subtasks (YAML format).
2. **Schedule** – Tasks are grouped into waves by dependency level; each wave runs in parallel.
3. **Execute** – Each wave's tasks are dispatched concurrently to their assigned LLM. A TUI monitor tracks progress.
4. **Collect** – Results are aggregated into a structured markdown report saved to the output directory.

## Project Structure

```
├── main.py              # Entry point
├── config/
│   ├── default.yaml     # Provider and model configuration
│   └── template.yaml    # Decomposer prompt template
├── src/
│   ├── models.py        # Pydantic data models
│   ├── config.py        # Config loader
│   ├── api_client.py    # LLM API client
│   ├── decomposer.py    # Problem decomposition
│   ├── scheduler.py     # Wave scheduling
│   ├── executor.py      # Parallel task execution
│   ├── collector.py     # Result aggregation
│   ├── orchestrator.py  # 4-phase orchestration
│   ├── cli.py           # Typer CLI
│   └── monitor.py       # TUI progress monitor
└── tests/               # Unit and integration tests
```

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_orchestrator.py -v
```