import os
import time
from typing import Any, Dict, List, Tuple

import httpx


class APIClient:
    def __init__(self, config: Dict[str, Any]):
        self.providers = config.get("providers", {})

    def _resolve(self, model_spec: str) -> Tuple[Dict[str, Any], str]:
        provider_name, model_name = model_spec.split(":", 1)
        provider = self.providers.get(provider_name, {})
        api_key = provider.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")
        return {
            "api_key": api_key,
            "base_url": provider.get("base_url", ""),
            "timeout": provider.get("timeout", 60),
            "retry_count": provider.get("retry_count", 3),
        }, model_name

    def chat(self, model_spec: str, messages: List[Dict[str, str]]) -> str:
        provider, model_name = self._resolve(model_spec)
        url = f"{provider['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model_name,
            "messages": messages,
        }
        max_retries = provider.get("retry_count", 3)
        last_error = None
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=provider.get("timeout", 60)) as client:
                    resp = client.post(url, json=body, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"API call failed after {max_retries} retries: {last_error}")