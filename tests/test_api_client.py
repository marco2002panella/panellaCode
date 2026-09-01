import os
from unittest.mock import MagicMock, patch

import httpx
from src.api_client import APIClient


def test_resolve_provider():
    client = APIClient(config={
        "providers": {
            "openai": {"api_key": "sk-test", "base_url": "https://api.openai.com/v1"},
        },
    })
    provider, model = client._resolve("openai:gpt-4o-mini")
    assert provider["api_key"] == "sk-test"
    assert provider["base_url"] == "https://api.openai.com/v1"
    assert model == "gpt-4o-mini"


def test_resolve_provider_env_var():
    os.environ["MY_API_KEY"] = "sk-from-env"
    try:
        client = APIClient(config={
            "providers": {
                "custom": {"api_key": "${MY_API_KEY}", "base_url": "https://custom.ai/v1"},
            },
        })
        provider, model = client._resolve("custom:my-model")
        assert provider["api_key"] == "sk-from-env"
        assert provider["base_url"] == "https://custom.ai/v1"
        assert model == "my-model"
    finally:
        del os.environ["MY_API_KEY"]


def test_resolve_provider_defaults():
    client = APIClient(config={
        "providers": {
            "minimal": {"api_key": "sk-min"},
        },
    })
    provider, model = client._resolve("minimal:model-x")
    assert provider["api_key"] == "sk-min"
    assert provider["base_url"] == ""
    assert provider["timeout"] == 60
    assert provider["retry_count"] == 3
    assert model == "model-x"


def test_chat_success():
    client = APIClient(config={
        "providers": {
            "openai": {"api_key": "sk-test", "base_url": "https://api.openai.com/v1"},
        },
    })
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}]
    }

    with patch("src.api_client.httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_client.return_value = mock_instance

        result = client.chat("openai:gpt-4o-mini", [{"role": "user", "content": "Hi"}])
        assert result == "Hello!"

        mock_instance.post.assert_called_once()
        call_kwargs = mock_instance.post.call_args
        assert call_kwargs[1]["json"]["model"] == "gpt-4o-mini"
        assert call_kwargs[1]["json"]["messages"] == [{"role": "user", "content": "Hi"}]


def test_chat_passes_reasoning_effort_when_configured():
    client = APIClient(config={
        "providers": {
            "regolo": {
                "api_key": "sk-test",
                "base_url": "https://api.regolo.ai/v1",
                "reasoning_effort": "low",
            },
        },
    })
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "[]"}}]
    }

    with patch("src.api_client.httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_client.return_value = mock_instance

        client.chat("regolo:qwen3.6-27b", [{"role": "user", "content": "Hi"}])
        assert mock_instance.post.call_args[1]["json"]["reasoning_effort"] == "low"


def test_chat_retry_on_failure():
    client = APIClient(config={
        "providers": {
            "openai": {"api_key": "sk-test", "base_url": "https://api.openai.com/v1", "retry_count": 2},
        },
    })
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Recovered!"}}]
    }

    with patch("src.api_client.httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.post.side_effect = [
            httpx.HTTPError("fail"),
            mock_response,
        ]
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_client.return_value = mock_instance

        with patch("src.api_client.time.sleep"):
            result = client.chat("openai:gpt-4o-mini", [{"role": "user", "content": "Hi"}])
            assert result == "Recovered!"
            assert mock_instance.post.call_count == 2


def test_chat_raises_after_max_retries():
    client = APIClient(config={
        "providers": {
            "openai": {"api_key": "sk-test", "base_url": "https://api.openai.com/v1", "retry_count": 2},
        },
    })

    with patch("src.api_client.httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.post.side_effect = httpx.HTTPError("permanent failure")
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_client.return_value = mock_instance

        with patch("src.api_client.time.sleep"):
            try:
                client.chat("openai:gpt-4o-mini", [{"role": "user", "content": "Hi"}])
                assert False, "Expected RuntimeError"
            except RuntimeError as e:
                assert "2 retries" in str(e)
                assert mock_instance.post.call_count == 2


def test_chat_falls_back_on_rate_limit():
    from src.zen_router import ZenRouter
    client = APIClient(config={
        "providers": {
            "opencode_zen": {"api_key": "sk-test", "base_url": "https://opencode.ai/zen/v1", "retry_count": 4},
        },
    }, router=ZenRouter(
        zen_free_models=["opencode_zen:big-pickle", "opencode_zen:nemotron-3-ultra-free"],
    ))

    def fake_post(url, json, headers):
        if json["model"] == "big-pickle":
            mock = MagicMock()
            mock.raise_for_status.side_effect = httpx.HTTPStatusError(
                "429 Free usage exceeded", request=httpx.Request("POST", url),
                response=httpx.Response(429, request=httpx.Request("POST", url)),
            )
            return mock
        mock = MagicMock()
        mock.raise_for_status = MagicMock(return_value=None)
        mock.json = MagicMock(return_value={
            "choices": [{"message": {"content": "OK from fallback"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        })
        return mock

    with patch("src.api_client.httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.post.side_effect = fake_post
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_client.return_value = mock_instance

        with patch("src.api_client.time.sleep"):
            result = client.chat("opencode_zen:big-pickle", [{"role": "user", "content": "Hi"}])
            assert result == "OK from fallback"
