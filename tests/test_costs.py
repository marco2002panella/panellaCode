from src.costs import CostTracker


def test_cost_tracker_calculates_configured_price():
    tracker = CostTracker({"regolo:qwen3.6-27b": {"input": 1.0, "output": 2.0}})
    tracker.record("decomposer", "regolo:qwen3.6-27b", 1000, 500)

    summary = tracker.summary()
    assert summary["input_tokens"] == 1000
    assert summary["output_tokens"] == 500
    assert summary["estimated_cost"] == 0.002
    assert summary["unknown_calls"] == 0


def test_cost_tracker_marks_missing_usage_or_price_unknown():
    tracker = CostTracker({})
    tracker.record("executor", "regolo:qwen3-coder-next", None, None)

    summary = tracker.summary()
    assert summary["estimated_cost"] is None
    assert summary["unknown_calls"] == 1
