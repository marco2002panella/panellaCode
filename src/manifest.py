import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import yaml


MANIFEST_FILENAME = "manifest.yaml"
STATE_FILENAME = "execution-state.yaml"
EXCLUDED_DIRECTORIES = {".git", ".venv", "venv", "output", "__pycache__", ".pytest_cache"}
EXCLUDED_FILES = {MANIFEST_FILENAME, STATE_FILENAME}
COMMENT_PREFIXES = {
    ".py": "#",
    ".sh": "#",
    ".yaml": "#",
    ".yml": "#",
    ".js": "//",
    ".jsx": "//",
    ".ts": "//",
    ".tsx": "//",
    ".java": "//",
    ".go": "//",
    ".rs": "//",
    ".c": "//",
    ".cpp": "//",
}


def _write_yaml(path: Path, data: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            yaml.safe_dump(data, stream, sort_keys=False, allow_unicode=False)
        os.replace(temporary, path)
    except Exception:
        os.unlink(temporary)
        raise
    return str(path)


def _relative_files(root: Path) -> List[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path.name in EXCLUDED_FILES:
            continue
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue
        files.append(relative)
    return sorted(files, key=lambda path: path.as_posix())


def build_manifest(root: str) -> Dict[str, Any]:
    project_root = Path(root).resolve()
    files = []
    for relative in _relative_files(project_root):
        suffix = relative.suffix.lower()
        language = "Python" if suffix == ".py" else ""
        files.append({
            "path": relative.as_posix(),
            "status": "existing",
            "role": "module" if language else "file",
            "purpose": "",
            "exports": [],
            "depends_on": [],
        })

    project_language = "Python" if any(item["path"].endswith(".py") for item in files) else "unknown"
    return {
        "version": 1,
        "project": {"root": ".", "language": project_language},
        "files": files,
    }


def save_manifest(root: str, manifest: Dict[str, Any]) -> str:
    return _write_yaml(Path(root) / MANIFEST_FILENAME, manifest)


def load_or_create_manifest(root: str) -> Dict[str, Any]:
    path = Path(root) / MANIFEST_FILENAME
    if path.exists():
        with path.open("r") as stream:
            return yaml.safe_load(stream) or build_manifest(root)
    manifest = build_manifest(root)
    save_manifest(root, manifest)
    return manifest


def manifest_context(manifest: Dict[str, Any]) -> str:
    context = {
        "project": manifest.get("project", {}),
        "files": [
            {
                key: entry.get(key)
                for key in ("path", "status", "role", "purpose", "exports", "depends_on")
                if key in entry
            }
            for entry in manifest.get("files", [])
        ],
    }
    return yaml.safe_dump(context, sort_keys=False, allow_unicode=False).strip()


def ensure_manifest_header(path: str, relative_path: str, purpose: str) -> bool:
    file_path = Path(path)
    prefix = COMMENT_PREFIXES.get(file_path.suffix.lower())
    if not prefix or not file_path.exists():
        return False
    content = file_path.read_text()
    if "[manifest-gen]" in "\n".join(content.splitlines()[:12]):
        return False

    header = (
        f"{prefix} [manifest-gen]\n"
        f"{prefix} path: {relative_path}\n"
        f"{prefix} purpose: {purpose}\n"
    )
    lines = content.splitlines(keepends=True)
    insertion = 1 if lines and lines[0].startswith("#!") else 0
    lines.insert(insertion, header)
    file_path.write_text("".join(lines))
    return True


def create_execution_state(root: str, problem: str, run_id: str) -> Dict[str, Any]:
    state = {"version": 1, "run_id": run_id, "problem": problem, "tasks": {}}
    _write_yaml(Path(root) / STATE_FILENAME, state)
    return state


def update_execution_state(root: str, state: Dict[str, Any], task_result: Dict[str, Any]) -> str:
    task_id = task_result["task_id"]
    state.setdefault("tasks", {})[task_id] = dict(task_result)
    return _write_yaml(Path(root) / STATE_FILENAME, state)
