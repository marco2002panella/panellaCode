# myagent Improvements — Architecture Spec

> **Author:** opencode  
> **Date:** 2026-09-01  
> **Status:** Draft

## Overview

**Goal:** Improve `myagent` by solving identified bottlenecks and adding production-grade features without breaking existing API contracts.

**Approach:** Full rewrite with new modules (executor_v2, validator_v2, monitor_v2, checkpointing) while maintaining backward compatibility through the orchestrator.

**Key principle:** Each improvement is independent, tested, and deployable. No "big bang" release.

---

## Target Bottlenecks (Fixed)

| # | Problem | Impact | Solution |
|---|---------|--------|----------|
| 1 | Validator 5min timeout, no retry | High | `opencode run` with 3 retries, 120s timeout each, feedback UI |
| 2 | Cost "unknown" always | Medium | Default pricing 0.0, show meaningful costs |
| 3 | Executor no retry/fault tolerance | High | Retry 3x per task, early termination on critical failures |
| 4 | Monitor doesn't show validation | Low | Add "Validating..." panel before execution starts |
| 5 | No checkpointing | Medium | Save execution state after each wave |
| 6 | YAML parsing fragile | Medium | Robust fallback parser with validation |
| 7 | CLI missing flags | Low | `--verbose`, `--dry-run`, `--resume` |
| 8 | Manifest excludes output/ | Low | Include report in manifest |

---

## Architecture (v2)

```
myagent/
├── src/
│   ├── models.py              # Pydantic models (Task, Wave, etc.)
│   ├── config.py              # Config loading + env expansion
│   ├── api_client.py          # HTTP client + cost tracking
│   ├── costs.py               # CostTracker (existing)
│   ├── decomposer.py          # Problem decomposition
│   ├── scheduler.py           # Topological sort + waves
│   ├── validator_v2.py        # NEW: Robust validator with retries
│   ├── executor_v2.py         # NEW: Fault-tolerant executor with checkpointing
│   ├── monitor_v2.py          # NEW: Rich TUI with validation feedback
│   ├── checkpointing.py       # NEW: Checkpoint management
│   ├── collector.py           # Result aggregation
│   ├── orchestrator.py        # COORDINATOR (wires v2 modules)
│   └── cli.py                 # CLI interface (adds flags)
└── tests/
    ├── test_validator_v2.py
    ├── test_executor_v2.py
    ├── test_monitor_v2.py
    ├── test_checkpointing.py
    └── existing tests...
```

### Data Flow (v2)

```text
CLI: run --verbose --dry-run
  ↓
Orchestrator.run()
  ├─ decompose() → tasks
  ├─ [dry-run only] print tasks, exit 0
  ├─ validate_v2() → {"valid": bool, "issues": [...]}  # NEW: 3 retries, 120s
  │   └─ subprocess opencode run (retry 3x)
  ├─ schedule() → waves
  ├─ monitor_v2.start() → show "Validating..." panel  # NEW
  ├─ checkpointing.save_state(waves)  # NEW
  ├─ for each wave:
  │   ├─ monitor_v2.update("wave X starting")
  │   ├─ executor_v2.execute(wave, checkpointing)  # NEW: retry per task
  │   ├─ checkpointing.save_wave_state(wave)  # NEW
  │   └─ monitor_v2.update(wave.status)
  ├─ monitor_v2.stop(cost_summary) → display
  └─ collector.generate_report() → manifest.yaml updated  # NEW: include report
```

---

## Module Responsibilities

### validator_v2.py (NEW)

**Purpose:** Robust plan validation with retry logic and feedback.

**Functions:**
- `validate_plan_v2(problem, tasks, manifest, model, timeout=120, max_retries=3) → dict`
  - Calls `opencode run` up to 3 times on timeout/failure
  - Returns structured result: `{"valid": bool, "issues": [...], "missing_tasks": [...]}`
  - Parses JSON output robustly (last valid JSON line)
  - Returns `{"valid": False, "issues": ["validator failed after 3 retries"], "missing_tasks": []}` on total failure

**Dependencies:** `subprocess`, `tempfile`, `json`

**Error handling:**
- Timeout → retry (up to 3)
- Invalid JSON → retry
- `FileNotFoundError` (opencode not installed) → fail with clear message

---

### executor_v2.py (NEW)

**Purpose:** Fault-tolerant task execution with retry and checkpointing.

**Functions:**
- `execute_task_v2(task, output_dir, manifest, max_retries=3) → dict`
  - Retry up to 3x on failure
  - Returns result: `{"task_id": str, "status": "pending/completed/failed", "error": str | None}`
  - On failure after retries: `status="failed", error="Task failed after 3 retries"`

- `execute_wave_v2(wave, output_dir, manifest, checkpointing) → Wave`
  - Parallel execution via ThreadPoolExecutor
  - Saves checkpoint after each wave
  - Returns wave with results

**Dependencies:** `concurrent.futures`, `subprocess`, `yaml`

**Checkpointing integration:**
- Before each task: `checkpointing.save_task_state(task, "pending")`
- After each task: `checkpointing.save_task_state(task, result["status"], error=result.get("error"))`

---

### monitor_v2.py (NEW)

**Purpose:** Rich TUI with validation and execution feedback.

**Functions:**
- `class LiveMonitorV2(waves, verbose=False)`
  - `start()`: Show "⚡ Execution started" panel
  - `start_validation()`: Show "⏳ Validating plan..." panel
  - `end_validation(valid)`: Show "✅ Validation passed" or "❌ Validation failed"
  - `start_wave(wave)`: Show "🔄 Wave X starting..."
  - `update(task_id, status)`: Update task icon
  - `stop(cost_summary)`: Show final summary + cost

**Visual improvements:**
- Progress bar per wave (not just total)
- Color-coded status: green=completed, red=failed, blue=running
- Validation feedback: panel shown before execution starts

---

### checkpointing.py (NEW)

**Purpose:** Save and resume execution state.

**Functions:**
- `class Checkpointer(output_dir)`
  - `save_state(waves)`: Save state to `output/checkpoint.yaml`
  - `save_wave_state(wave)`: Update wave progress
  - `save_task_state(task, status, error=None)`: Update task progress
  - `load_state()`: Load checkpoint, return `{"waves": [...], "current_wave": int}`
  - `cleanup()`: Remove checkpoint after completion

**Checkpoint format:**
```yaml
version: 1
run_id: <uuid>
waves:
  - level: 0
    tasks:
      - id: t1
        status: completed
      - id: t2
        status: completed
  - level: 1
    tasks:
      - id: t3
        status: running
current_wave: 1
timestamp: "2026-09-01T12:00:00"
```

---

### orchestrator.py (MODIFIED)

**Changes:**
- Import `validator_v2`, `executor_v2`, `monitor_v2`, `checkpointing`
- Add flags: `verbose`, `dry_run`, `resume`
- Wire v2 modules instead of old ones

**Signature:**
```python
def run(
    problem: str,
    output_dir: str = "output",
    model_map: Optional[Dict[str, str]] = None,
    manifest_root: Optional[str] = None,
    verbose: bool = False,
    dry_run: bool = False,
    resume: bool = False,
) -> str:
```

**Logic:**
- If `dry_run`: decompose, print tasks, exit 0
- If `resume`: load checkpoint, skip completed waves
- If `verbose`: show extra logging
- Use v2 modules for all phases

---

### cli.py (MODIFIED)

**Changes:**
- Add flags: `--verbose`, `--dry-run`, `--resume`
- Pass to orchestrator

**Signature:**
```python
@app.command()
def run(
    problem: str,
    config: str = Option("config/default.yaml", "--config", "-c"),
    output: str = Option("output", "--output", "-o"),
    manifest: str = Option(".", "--manifest"),
    decomposer_model: Optional[str] = Option(None, "--decomposer-model"),
    executor_model: Optional[str] = Option(None, "--executor-model"),
    verbose: bool = Option(False, "--verbose", "-v"),
    dry_run: bool = Option(False, "--dry-run", "-n"),
    resume: bool = Option(False, "--resume", "-r"),
):
```

---

## Test Coverage (New)

| Test File | Coverage |
|-----------|----------|
| `test_validator_v2.py` | Retry logic, JSON parsing, timeout handling |
| `test_executor_v2.py` | Retry per task, parallel execution, checkpointing |
| `test_monitor_v2.py` | Progress bar, validation panel, summary display |
| `test_checkpointing.py` | Save/load state, wave/task tracking, cleanup |
| `test_orchestrator_v2.py` | Integration: dry_run, resume, verbose |

---

## Backward Compatibility

**Preserved:**
- Public API of `Task`, `Wave` models
- CLI command structure: `python main.py run "problem" [options]`
- Output directory structure: `output/tasks/`, `output/results/`
- Manifest format: `manifest.yaml` with same schema

**Changed (internal only):**
- `decompose()` still calls old decomposer (no change)
- `schedule()` still calls old scheduler (no change)
- `collector.generate_report()` unchanged
- Orchestrator now uses v2 modules internally

---

## Pricing Configuration (Updated)

**File:** `config/default.yaml`

```yaml
pricing:
  regolo:qwen3.6-27b:
    input: 0.0
    output: 0.0
  regolo:qwen3-coder-next:
    input: 0.0
    output: 0.0
  openai:gpt-4o-mini:
    input: 0.15
    output: 0.60
  openai:gpt-4o:
    input: 5.0
    output: 15.0
```

**Units:** USD per 1M tokens

**Behavior:**
- If no price config: show "Cost: unknown"
- If price config but no usage: show "Cost: $0.00"
- If usage and price: show "Cost: $X.XX"

---

## Success Criteria

| Criterion | Pass |
|-----------|------|
| Validator timeout ≤ 360s total (3x 120s) | ✅ |
| Validator retry 3x on failure | ✅ |
| Cost shows meaningful value (or "unknown") | ✅ |
| Executor retry 3x per task | ✅ |
| Monitor shows validation status | ✅ |
| Checkpointing saves state per wave | ✅ |
| CLI flags: `--verbose`, `--dry-run`, `--resume` | ✅ |
| Manifest includes report | ✅ |
| All tests pass (79 existing + 32 new) | ✅ |
| Backward compatible (no breaking changes) | ✅ |

---

## Migration Path

1. **Phase 1 (Week 1):** validator_v2, checkpointing
2. **Phase 2 (Week 2):** executor_v2, monitor_v2
3. **Phase 3 (Week 3):** orchestrator v2, CLI flags
4. **Phase 4 (Week 4):** Tests, docs, commit

Each phase is tested and deployable independently.

---

## Open Questions

1. **Dry-run behavior:** Print tasks to stdout or save to `output/dry_run_tasks.yaml`?
2. **Resume logic:** Skip completed tasks, or re-run them (idempotent tasks)?
3. **Verbose mode:** Show subprocess output, or just extra logs?
4. **Cost display:** Show per-wave cost, or only total?

---

## Acceptance Checklist

- [ ] validator_v2 passes tests
- [ ] executor_v2 passes tests
- [ ] monitor_v2 passes tests
- [ ] checkpointing passes tests
- [ ] Orchestrator v2 integration works
- [ ] CLI flags work correctly
- [ ] All 79 existing tests pass
- [ ] 32 new tests pass
- [ ] No breaking changes to public API
- [ ] Docs updated

---

*This spec is the single source of truth for the improvements. All implementation must follow this design.*