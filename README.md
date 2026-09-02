# problemSolver

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
# Launch the GUI (type a problem and press Enter)
python main.py

# Solve a problem
python main.py run "Build a REST API with FastAPI for a todo app"

# Custom config and output directory
python main.py run "Create a React dashboard" -c config/my.yaml -o my_output

# Use a repository manifest for independent calls
python main.py run "Create a graph project" --manifest /path/to/project

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

## Repository Context

Each run can maintain two files in the working project directory:

- `manifest.yaml` describes the repository tree, file roles, purposes, and dependencies.
- `execution-state.yaml` records the problem, task statuses, result paths, and errors.

The manifest is included in the decomposer and executor prompts as bounded context. It is metadata only: file contents are loaded only when a task explicitly references them. The scanner excludes `.git`, virtual environments, caches, and `output/`.

Before scheduling, `opencode` always validates the generated plan against the original problem and manifest. An invalid or unparsable validation response stops the run before any task is dispatched.

The execution UI shows token usage and estimated cost when provider pricing and usage metadata are available. Unknown costs are reported as `unknown` rather than guessed. Configure prices in `config/default.yaml` under `pricing` using input and output cost per million tokens.

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

## Improvements

### Robust Validation
Plans are validated using `opencode` with retry logic (up to 3 retries, 120s timeout each).

### Cost Tracking
Configure pricing in `config/default.yaml` under `pricing`. Costs are displayed per million tokens.

### Checkpointing & Resume
Execution state is saved after each wave. Use `--resume` to continue from where you left off.

### CLI Flags
- `--verbose`, `-v`: Enable verbose output
- `--dry-run`, `-n`: Show tasks without executing
- `--resume`, `-r`: Resume from checkpoint

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_orchestrator.py -v
```
