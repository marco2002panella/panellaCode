from src.config import load_config


def test_load_config_has_pricing():
    cfg = load_config("config/default.yaml")
    assert "pricing" in cfg
    assert "opencode_zen:big-pickle" in cfg["pricing"]
    assert "regolo:qwen3.8-27b" in cfg["pricing"]