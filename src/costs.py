from typing import Dict, Optional


class CostTracker:
    def __init__(self, pricing: Optional[Dict] = None):
        self.pricing = pricing or {}
        self.calls = []

    def record(
        self,
        role: str,
        model: str,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
    ) -> None:
        price = self.pricing.get(model, {})
        cost = None
        if input_tokens is not None and output_tokens is not None:
            if "input" in price and "output" in price:
                cost = (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
        self.calls.append({
            "role": role,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": cost,
        })

    def summary(self) -> Dict:
        known_costs = [call["estimated_cost"] for call in self.calls if call["estimated_cost"] is not None]
        return {
            "calls": len(self.calls),
            "input_tokens": sum(call["input_tokens"] or 0 for call in self.calls),
            "output_tokens": sum(call["output_tokens"] or 0 for call in self.calls),
            "estimated_cost": round(sum(known_costs), 6) if known_costs else None,
            "unknown_calls": sum(1 for call in self.calls if call["estimated_cost"] is None),
        }
