# Repository Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repository and execution manifests so independent model calls receive explicit project context and failures can be diagnosed against known files.

**Architecture:** `src/manifest.py` scans the caller's working directory into a compact `manifest.yaml`, validates and updates file metadata, and stores per-run task state in `execution-state.yaml`. `decomposer.py`, `orchestrator.py`, and `executor.py` consume bounded manifest context; the collector persists task results and synchronizes generated files.

**Tech Stack:** Python 3.12+, PyYAML, Pydantic models, pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-repository-manifest-design.md`

## Global Constraints

- Exclude `.git`, `.venv`, `venv`, `output`, `__pycache__`, and dependency caches from scans.
- Keep `manifest.yaml` and `execution-state.yaml` in the caller's working directory.
- Keep model context bounded to manifest metadata and task-related paths.
- Preserve existing CLI behavior and all current tests.

---

### Task 1: Manifest Data Model And Scanner

**Files:**
- Create: `src/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- `build_manifest(root: str) -> dict`
- `load_or_create_manifest(root: str) -> dict`
- `save_manifest(root: str, manifest: dict) -> str`
- `manifest_context(manifest: dict) -> str`

- [ ] **Step 1: Write failing tests** for excluded directories, stable relative paths, load/create behavior, and compact context output.
- [ ] **Step 2: Run `python3 -m pytest tests/test_manifest.py -q` and verify collection fails because `src.manifest` is missing.
- [ ] **Step 3: Implement the scanner with `pathlib.Path.rglob`, excluded directory names, YAML persistence, and deterministic sorted file records.
- [ ] **Step 4: Run the targeted tests and verify they pass.

### Task 2: Execution State Persistence

**Files:**
- Modify: `src/manifest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- `create_execution_state(root: str, problem: str, run_id: str) -> dict`
- `update_execution_state(root: str, state: dict, task_result: dict) -> str`

- [ ] **Step 1: Add failing tests** asserting task results are merged by `task_id` and written to `execution-state.yaml`.
- [ ] **Step 2: Run the targeted tests and verify the new assertions fail.
- [ ] **Step 3: Implement atomic YAML writes and task result updates.
- [ ] **Step 4: Run `python3 -m pytest tests/test_manifest.py -q` and verify it passes.

### Task 3: Reasoner Context Integration

**Files:**
- Modify: `src/decomposer.py`, `src/orchestrator.py`
- Test: `tests/test_decomposer.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Extend `decompose(problem, client, model_spec, repair_model_spec=None, manifest=None)` without breaking existing callers.

- [ ] **Step 1: Add failing tests** verifying the decomposer prompt includes manifest paths and roles when provided.
- [ ] **Step 2: Run targeted tests and verify the prompt assertions fail.
- [ ] **Step 3: Add the optional manifest context to the prompt and have the orchestrator load/create the manifest in the current working directory.
- [ ] **Step 4: Run the targeted tests and verify they pass.

### Task 4: Executor Context And State Updates

**Files:**
- Modify: `src/executor.py`, `src/orchestrator.py`
- Test: `tests/test_executor.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Extend `build_opencode_prompt(task, manifest=None) -> str`.
- Extend `execute_wave_parallel(wave, output_dir, manifest=None, state_callback=None) -> Wave`.

- [ ] **Step 1: Add failing tests** verifying a task prompt includes its manifest entry and the callback receives each result.
- [ ] **Step 2: Run targeted tests and verify they fail.
- [ ] **Step 3: Implement bounded manifest context and invoke the execution-state callback for completed and failed futures.
- [ ] **Step 4: Run targeted tests and verify they pass.

### Task 5: CLI Working Directory And Documentation

**Files:**
- Modify: `src/cli.py`, `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add a failing CLI test** asserting `--manifest` defaults to the current directory and can be overridden.
- [ ] **Step 2: Run the targeted test and verify it fails.
- [ ] **Step 3: Add the option and document `manifest.yaml`, `execution-state.yaml`, exclusions, and independent calls.
- [ ] **Step 4: Run the full suite with `python3 -m pytest tests/ -q`.
- [ ] **Step 5: Run `python3 -m py_compile src/manifest.py src/decomposer.py src/executor.py src/orchestrator.py`.
