import os
from pathlib import Path
from typing import Any, Dict
import yaml
from src.models import TaskTemplate


def _expand_env_vars(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")
    return value


def _expand_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _expand_dict(v)
        else:
            result[k] = _expand_env_vars(v)
    return result


def load_config(path: str = "config/default.yaml") -> Dict[str, Any]:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return _expand_dict(raw)


def load_template(path: str = "config/template.yaml") -> TaskTemplate:
    template_path = Path(path)
    if path == "config/template.yaml" and not template_path.exists():
        template_path = Path(__file__).resolve().parent.parent / path
    with open(template_path, "r") as f:
        raw = yaml.safe_load(f)
    return TaskTemplate(**raw)
