from src.config import load_config, load_template


def test_load_default_config():
    cfg = load_config("config/default.yaml")
    assert "providers" in cfg
    assert "openai" in cfg["providers"]
    assert "models" in cfg
    assert cfg["models"]["decomposer"] == "regolo:qwen3.6-27b"
    assert cfg["models"]["task_repair"] == "regolo:qwen3-coder-next"


def test_load_template():
    template = load_template("config/template.yaml")
    assert isinstance(template.fields, list)
    assert len(template.decomposer_instructions) > 0


def test_load_template_default_is_independent_of_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    template = load_template()
    assert len(template.decomposer_instructions) > 0
