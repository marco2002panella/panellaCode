# Interactive TUI Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix interactive TUI mode to properly handle manifest_root and avoid API key errors.

**Root cause:** `_decompose_with_repair` doesn't receive `manifest_root` so it can't load repository context.

**Fix:** Update `_decompose_with_repair` to accept `manifest_root` parameter.

---

### Task 1: Fix orchestrator.py _decompose_with_repair

**Files:**
- Modify: `src/orchestrator.py`

**Interfaces:**
- Consumes: `load_config`, `load_or_create_manifest`, `manifest_context`
- Produces: `_decompose_with_repair(problem, manifest_root)` that loads repository_context

- [ ] **Step 1: Update _decompose_with_repair**

Change from:
```python
def _decompose_with_repair(self, problem: str, repository_context: str = None):
```

To:
```python
def _decompose_with_repair(self, problem: str, manifest_root: str = None):
    from src.decomposer import decompose
    from src.config import load_config
    from src.manifest import load_or_create_manifest, manifest_context
    
    config = load_config()
    model_config = config.get("models", {})
    decomposer_model = model_config.get("decomposer", "openai:gpt-4o-mini")
    repair_model = model_config.get("task_repair", model_config.get("executor_default", "openai:gpt-4o-mini"))
    
    repository_context = None
    if manifest_root:
        manifest = load_or_create_manifest(manifest_root)
        repository_context = manifest_context(manifest)
    
    return decompose(problem, self.client, decomposer_model, repair_model, repository_context)
```

- [ ] **Step 2: Update interactive_session.py to pass manifest_root**

```python
session = InteractiveSession(orch, problem, output, manifest_root=manifest)
```

And add to `__init__`:
```python
def __init__(self, orchestrator: Orchestrator, problem: str, output_dir: str, manifest_root: str = None):
    ...
    self.manifest_root = manifest_root
```

And update `run()`:
```python
tasks = self.orchestrator._decompose_with_repair(self.problem, self.manifest_root)
```

- [ ] **Step 3: Update cli.py to pass manifest**

```python
session = InteractiveSession(orch, problem, output, manifest_root=manifest)
```

- [ ] **Step 4: Commit**

```bash
git add src/orchestrator.py src/interactive_session.py src/cli.py
git commit -m "fix: interactive TUI manifest_root handling"
```

---

## Summary

| File | Change |
|------|--------|
| `src/orchestrator.py` | `_decompose_with_repair` now accepts `manifest_root` |
| `src/interactive_session.py` | Accept `manifest_root`, pass to orchestrator |
| `src/cli.py` | Pass `manifest` to InteractiveSession |