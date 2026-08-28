from src.config import load_config, load_template


def test_load_default_config():
    cfg = load_config("config/default.yaml")
    assert "providers" in cfg
    assert "openai" in cfg["providers"]
    assert "models" in cfg


def test_load_template():
    template = load_template("config/template.yaml")
    assert isinstance(template.fields, list)
    assert len(template.decomposer_instructions) > 0