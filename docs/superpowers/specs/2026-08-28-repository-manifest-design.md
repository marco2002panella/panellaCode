# Repository Manifest Design

## Goal

Give each independent reasoner call a compact, explicit description of the working repository and preserve execution state separately from repository metadata.

## Design

`manifest.yaml` lives in the current working directory and describes the project tree, file roles, purposes, exports, dependencies, and lifecycle status. `execution-state.yaml` records the current problem, task results, generated artifacts, and errors for one run. The reasoner receives the manifest and a bounded context excerpt; it does not depend on conversation history.

## Requirements

- Generate or update `manifest.yaml` in the caller's working directory.
- Never include file contents in the manifest; record paths and metadata only.
- Keep execution state in `execution-state.yaml`, separate from repository metadata.
- Update execution state after each task result is collected.
- Preserve existing `[manifest-gen]` headers when present and support language-specific comment syntax for generated files.
- Treat the manifest as advisory context; parser and scheduler validation remain authoritative.
- Do not scan dependency caches, virtual environments, `.git`, or output directories.

## Data Model

```yaml
version: 1
project:
  root: .
  language: Python
files:
  - path: src/example.py
    status: generated
    role: module
    purpose: Short description
    exports: []
    depends_on: []
```

Execution state uses a stable `run_id`, the original problem, and task records keyed by task ID. File records use `planned`, `generated`, `modified`, or `deleted` status.

## Context Policy

The decomposer prompt includes the manifest summary and the current problem. The executor prompt includes the manifest entry and related file paths for its task. The system never sends the entire repository automatically.
