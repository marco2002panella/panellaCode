from typing import Dict, List
from collections import defaultdict, deque
from src.models import Task, Wave


class CycleError(Exception):
    pass


def topological_sort(tasks: List[Task]) -> List[str]:
    task_map = {t.id: t for t in tasks}
    in_degree: Dict[str, int] = {t.id: 0 for t in tasks}
    dependents: Dict[str, List[str]] = defaultdict(list)

    for t in tasks:
        for dep in t.dependencies:
            if dep not in task_map:
                continue
            dependents[dep].append(t.id)
            in_degree[t.id] += 1

    queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for dependent in dependents[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(tasks):
        remaining = set(t.id for t in tasks) - set(result)
        raise CycleError(f"Cycle detected among tasks: {remaining}")

    return result


def schedule(tasks: List[Task]) -> List[Wave]:
    if not tasks:
        return []

    topological_sort(tasks)
    task_map = {t.id: t for t in tasks}
    levels: Dict[str, int] = {}

    def get_level(tid: str) -> int:
        if tid in levels:
            return levels[tid]
        task = task_map[tid]
        valid_deps = [dep for dep in task.dependencies if dep in task_map]
        if not valid_deps:
            levels[tid] = 0
            return 0
        max_dep_level = max(get_level(dep) for dep in valid_deps)
        levels[tid] = max_dep_level + 1
        return levels[tid]

    for t in tasks:
        get_level(t.id)

    wave_map: Dict[int, List[Task]] = defaultdict(list)
    for t in tasks:
        t.level = levels[t.id]
        wave_map[levels[t.id]].append(t)

    waves = []
    for level in sorted(wave_map.keys()):
        waves.append(Wave(level=level, tasks=wave_map[level], status="pending"))

    return waves
