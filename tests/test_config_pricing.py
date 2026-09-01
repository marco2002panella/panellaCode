from src.config import load_config


def test_load_config_has_pricing():
    cfg = load_config("config/default.yaml")
    assert "pricing" in cfg
    assert "regolo:qwen3-coder-next" in cfg["pricing"]