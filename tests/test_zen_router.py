# tests/test_zen_router.py
from src.zen_router import ZenRouter, to_opencode_model

FREE = [
    "opencode_zen:big-pickle",
    "opencode_zen:nemotron-3-ultra-free",
    "opencode_zen:nemotron-3.5-lightning-free",
    "opencode_zen:ling-3.0-flash-fin-free",
    "opencode_zen:mimo-v2.5-free",
]
REGOLO = [
    "regolo:qwen3.8-27b",
    "regolo:qwen3-coder-next",
    "regolo:gpt-oss-120b",
    "regolo:gpt-oss-20b",
]


def test_chain_ordered_free_then_regolo():
    router = ZenRouter(FREE, REGOLO)
    assert router.chain == FREE + REGOLO


def test_next_for_role_returns_first_available():
    router = ZenRouter(FREE, REGOLO)
    assert router.next_for_role() == "opencode_zen:big-pickle"


def test_rotate_for_wave_round_robin():
    router = ZenRouter(FREE, REGOLO)
    assert router.rotate_for_wave(0) == FREE[0]
    assert router.rotate_for_wave(5) == FREE[0]
    assert router.rotate_for_wave(6) == FREE[1]


def test_next_fallback_advances_through_catena():
    router = ZenRouter(FREE, REGOLO)
    current = FREE[0]
    assert router.next_fallback(current) == FREE[1]
    current = FREE[4]
    assert router.next_fallback(current) == REGOLO[0]
    current = REGOLO[3]
    assert router.next_fallback(current) is None


def test_register_failure_removes_from_chain():
    router = ZenRouter(FREE, REGOLO)
    router.register_failure(FREE[0])
    assert FREE[0] not in router.chain
    assert router.next_for_role() == FREE[1]


def test_register_failure_walks_to_regolo_fallback():
    router = ZenRouter(FREE, REGOLO)
    for m in FREE:
        router.register_failure(m)
    assert router.next_for_role() == REGOLO[0]


def test_all_fail_reset_to_first():
    router = ZenRouter(FREE, REGOLO)
    for m in FREE + REGOLO:
        router.register_failure(m)
    assert router.next_for_role() == FREE[0]


def test_reset_clears_failures():
    router = ZenRouter(FREE, REGOLO)
    router.register_failure(FREE[0])
    router.reset()
    assert router.chain == FREE + REGOLO


def test_is_rate_limit_detects_markers():
    assert ZenRouter.is_rate_limit("HTTP 429 rate limit exceeded")
    assert ZenRouter.is_rate_limit("Free usage exceeded, add credits")
    assert ZenRouter.is_rate_limit("FreeUsageLimitError: Rate limit exceeded")
    assert ZenRouter.is_rate_limit("Retry-After: 3600")
    assert not ZenRouter.is_rate_limit("task timed out")
    assert not ZenRouter.is_rate_limit("")


def test_to_opencode_model_zen_strips_provider():
    assert to_opencode_model("opencode_zen:big-pickle") == "big-pickle"
    assert to_opencode_model("opencode_zen:nemotron-3-ultra-free") == "nemotron-3-ultra-free"


def test_to_opencode_model_regolo_alias():
    assert to_opencode_model("regolo:qwen3-coder-next") == "regolo-ai/qwen3-coder-next"


def test_to_opencode_model_other_provider_pass_through():
    assert to_opencode_model("openai:gpt-4o-mini") == "openai/gpt-4o-mini"


def test_to_opencode_model_no_colon_passthrough():
    assert to_opencode_model("big-pickle") == "big-pickle"


def test_executor_default_included_first():
    router = ZenRouter([], REGOLO, executor_default="opencode_zen:big-pickle")
    assert router.zen_free_models[0] == "opencode_zen:big-pickle"