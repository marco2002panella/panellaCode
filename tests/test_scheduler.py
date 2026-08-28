from src.scheduler import topological_sort, schedule, CycleError
from src.models import Task


def _make_task(tid: str, deps: list = None) -> Task:
    return Task(
        id=tid,
        description=tid,
        context={"project_root": "/x", "output_file": f"{tid}.py", "related_files": []},
        conventions={"framework": "", "language": "", "style": "", "code_split": []},
        dependencies=deps or [],
        level=0,
        assigned_model="default",
    )


def test_topo_linear():
    tasks = [
        _make_task("t1"),
        _make_task("t2", ["t1"]),
        _make_task("t3", ["t2"]),
    ]
    order = topological_sort(tasks)
    assert order.index("t1") < order.index("t2")
    assert order.index("t2") < order.index("t3")


def test_topo_parallel():
    tasks = [
        _make_task("t1"),
        _make_task("t2"),
        _make_task("t3", ["t1", "t2"]),
    ]
    waves = schedule(tasks)
    assert len(waves) == 2
    assert waves[0].level == 0
    assert {w.id for w in waves[0].tasks} == {"t1", "t2"}
    assert waves[1].level == 1
    assert {w.id for w in waves[1].tasks} == {"t3"}


def test_topo_diamond():
    tasks = [
        _make_task("t1"),
        _make_task("t2", ["t1"]),
        _make_task("t3", ["t1"]),
        _make_task("t4", ["t2", "t3"]),
    ]
    waves = schedule(tasks)
    assert len(waves) == 3
    assert {w.id for w in waves[0].tasks} == {"t1"}
    assert {w.id for w in waves[1].tasks} == {"t2", "t3"}
    assert {w.id for w in waves[2].tasks} == {"t4"}


def test_topo_cycle_raises():
    t1 = _make_task("t1", ["t2"])
    t2 = _make_task("t2", ["t1"])
    try:
        topological_sort([t1, t2])
        assert False, "Should have raised CycleError"
    except CycleError:
        pass