import os
import tempfile

from src.collector import collect_results, generate_report, save_report
from src.models import Task, Wave


def _make_task(tid: str) -> Task:
    return Task(
        id=tid,
        description=f"Task {tid}",
        context={"project_root": "/x", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=[],
        level=0,
        assigned_model="default",
    )


def test_generate_report():
    waves = [
        Wave(
            level=0,
            tasks=[_make_task("t1"), _make_task("t2")],
            status="completed",
        ),
        Wave(
            level=1,
            tasks=[_make_task("t3")],
            status="completed",
        ),
    ]
    report = generate_report(waves)
    assert "Wave 0" in report
    assert "Wave 1" in report
    assert "t1" in report
    assert "t3" in report


def test_generate_report_with_task_results():
    waves = [
        Wave(
            level=0,
            tasks=[_make_task("t1")],
            status="completed",
            task_results=[
                {"task_id": "t1", "status": "completed"},
            ],
        ),
    ]
    report = generate_report(waves)
    assert "COMPLETED" in report


def test_generate_report_with_failed_task():
    waves = [
        Wave(
            level=0,
            tasks=[_make_task("t1")],
            status="failed",
            task_results=[
                {"task_id": "t1", "status": "failed", "error": "timeout"},
            ],
        ),
    ]
    report = generate_report(waves)
    assert "FAILED" in report
    assert "timeout" in report


def test_generate_report_empty_waves():
    report = generate_report([])
    assert "Execution Report" in report
    assert "Total tasks: 0" in report


def test_collect_results():
    waves = [
        Wave(
            level=0,
            tasks=[_make_task("t1")],
            status="completed",
            task_results=[
                {"task_id": "t1", "status": "completed"},
            ],
        ),
        Wave(
            level=1,
            tasks=[_make_task("t2")],
            status="completed",
            task_results=[
                {"task_id": "t2", "status": "completed"},
            ],
        ),
    ]
    results = collect_results(waves, "/tmp/output")
    assert len(results) == 2
    assert results[0]["task_id"] == "t1"
    assert results[1]["task_id"] == "t2"


def test_save_report_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        report = "# Test Report"
        path = save_report(report, tmpdir)
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == "# Test Report"


def test_save_report_custom_filename():
    with tempfile.TemporaryDirectory() as tmpdir:
        report = "# Custom"
        path = save_report(report, tmpdir, filename="custom.md")
        assert path.endswith("custom.md")
