from pathlib import Path

from src.manifest import (
    build_manifest,
    create_execution_state,
    load_or_create_manifest,
    manifest_context,
    save_manifest,
    update_execution_state,
    ensure_manifest_header,
)


def test_build_manifest_excludes_generated_and_dependency_directories(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "venv").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "src" / "app.py").write_text("def run():\n    pass\n")
    (tmp_path / ".git" / "ignored").write_text("ignored")
    (tmp_path / "venv" / "ignored.py").write_text("ignored")
    (tmp_path / "output" / "report.md").write_text("ignored")

    manifest = build_manifest(str(tmp_path))

    assert [entry["path"] for entry in manifest["files"]] == ["src/app.py"]
    assert manifest["version"] == 1


def test_load_or_create_manifest_persists_deterministic_yaml(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n")

    first = load_or_create_manifest(str(tmp_path))
    second = load_or_create_manifest(str(tmp_path))

    assert first == second
    assert (tmp_path / "manifest.yaml").exists()


def test_save_manifest_and_context_are_compact(tmp_path):
    manifest = {
        "version": 1,
        "project": {"root": ".", "language": "Python"},
        "files": [{"path": "app.py", "role": "module", "purpose": "Runs app"}],
    }

    path = save_manifest(str(tmp_path), manifest)
    context = manifest_context(manifest)

    assert Path(path) == tmp_path / "manifest.yaml"
    assert "app.py" in context
    assert "Runs app" in context
    assert len(context) < 500


def test_execution_state_updates_task_results(tmp_path):
    state = create_execution_state(str(tmp_path), "Build an app", "run-1")
    update_execution_state(
        str(tmp_path),
        state,
        {"task_id": "task_001", "status": "completed", "result_path": "output.md"},
    )

    assert state["run_id"] == "run-1"
    assert state["tasks"]["task_001"]["status"] == "completed"
    assert (tmp_path / "execution-state.yaml").exists()


def test_ensure_manifest_header_uses_language_comment_and_preserves_shebang(tmp_path):
    source = tmp_path / "tool.py"
    source.write_text("#!/usr/bin/env python3\nprint('ok')\n")

    ensure_manifest_header(str(source), "tool.py", "Runs the tool")
    ensure_manifest_header(str(source), "tool.py", "Runs the tool")

    content = source.read_text()
    assert content.startswith("#!/usr/bin/env python3\n# [manifest-gen]")
    assert content.count("[manifest-gen]") == 1
    assert "# purpose: Runs the tool" in content
