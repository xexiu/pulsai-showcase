"""Behaviour tests for OllamaAIProvider — the local Ollama ``/api/chat`` integration.

RED-FIRST: written before ``src/infrastructure/ai/ai_provider_ollama.py`` existed, so the first
run of this file must fail with ``ModuleNotFoundError``. HTTP is fully mocked (patching the
module's own ``httpx.get`` / ``httpx.post``) — no socket, no real Ollama server, fast and
deterministic.

Covers the four behaviours the task calls out explicitly: message-content extraction from a chat
response, a non-JSON reply handled without crashing the caller, the shared outbound timeout
constant honoured on every call, and ``is_configured()`` reading False when the local server is
unreachable.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.infrastructure.ai.ai_provider_base import AIProviderUpstreamError
from src.shared.constants.ai_provider_http import AI_PROVIDER_REQUEST_TIMEOUT_SECONDS


def _fake_response(
    json_data: dict[str, Any] | None = None,
    *,
    json_error: Exception | None = None,
) -> MagicMock:
    """A minimal stand-in for ``httpx.Response`` — only the surface this provider touches."""
    response = MagicMock()
    response.raise_for_status.return_value = None
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = json_data or {}
    return response


def _configured_provider(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Build an OllamaAIProvider whose construction-time reachability probe succeeds."""
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider

    with patch(
        "src.infrastructure.ai.ai_provider_ollama.httpx.get",
        return_value=_fake_response({"version": "0.33.3"}),
    ):
        return OllamaAIProvider()


class TestBaseUrlResolution:
    """No hardcoded URL — env var first, a named default constant otherwise."""

    def test_default_base_url_used_when_env_var_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider
        from src.infrastructure.ai.ai_provider_ollama_constants import DEFAULT_OLLAMA_BASE_URL

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.get",
            return_value=_fake_response({"version": "0.33.3"}),
        ) as mock_get:
            provider = OllamaAIProvider()

        called_url = mock_get.call_args.args[0]
        assert called_url == f"{DEFAULT_OLLAMA_BASE_URL}/api/version"
        assert provider.is_configured() is True

    def test_env_var_overrides_the_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://example-host:9999")
        from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.get",
            return_value=_fake_response({"version": "0.33.3"}),
        ) as mock_get:
            OllamaAIProvider()

        called_url = mock_get.call_args.args[0]
        assert called_url == "http://example-host:9999/api/version"


class TestIsConfigured:
    """ "Configured" means the local server answered — there is no API key to check instead."""

    def test_true_when_the_server_answers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _configured_provider(monkeypatch)
        assert provider.is_configured() is True

    def test_false_when_the_server_is_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The behaviour the task calls out explicitly: a dead local server must not read as configured."""
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.get",
            side_effect=httpx.ConnectError("no route to host"),
        ):
            provider = OllamaAIProvider()

        assert provider.is_configured() is False

    def test_reachability_probe_honours_the_shared_timeout_constant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same constant Groq/OpenRouter were fixed to use in commit c2e25c565 — not a new number."""
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.get",
            return_value=_fake_response({"version": "0.33.3"}),
        ) as mock_get:
            OllamaAIProvider()

        assert mock_get.call_args.kwargs["timeout"] == AI_PROVIDER_REQUEST_TIMEOUT_SECONDS


class TestClassifySync:
    """``_classify_sync`` is what ``llm_market_decision.decide_all`` calls directly."""

    def test_extracts_message_content_from_the_chat_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _configured_provider(monkeypatch)
        payload = {"message": {"role": "assistant", "content": "OK"}}

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.post",
            return_value=_fake_response(payload),
        ):
            result = provider._classify_sync(system="sys", user="Reply with the single word OK", max_tokens=16, model=None, temperature=0.0)

        assert result == "OK"

    def test_chat_call_honours_the_shared_timeout_constant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _configured_provider(monkeypatch)
        payload = {"message": {"content": "OK"}}

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.post",
            return_value=_fake_response(payload),
        ) as mock_post:
            provider._classify_sync(system="sys", user="ping", max_tokens=None, model=None, temperature=None)

        assert mock_post.call_args.kwargs["timeout"] == AI_PROVIDER_REQUEST_TIMEOUT_SECONDS

    def test_model_and_generation_options_are_forwarded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _configured_provider(monkeypatch)
        payload = {"message": {"content": "OK"}}

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.post",
            return_value=_fake_response(payload),
        ) as mock_post:
            provider._classify_sync(
                system="sys",
                user="ping",
                max_tokens=16,
                model="qwen2.5:14b-instruct",
                temperature=0.0,
            )

        sent_json = mock_post.call_args.kwargs["json"]
        assert sent_json["model"] == "qwen2.5:14b-instruct"
        assert sent_json["stream"] is False
        assert sent_json["options"]["temperature"] == 0.0
        assert sent_json["options"]["num_predict"] == 16
        assert sent_json["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "ping"},
        ]

    def test_non_json_reply_raises_ai_provider_upstream_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A broken/misbehaving local server must not crash the caller with a raw JSONDecodeError."""
        provider = _configured_provider(monkeypatch)
        broken_response = _fake_response(json_error=ValueError("Expecting value: line 1 column 1"))

        with (
            patch(
                "src.infrastructure.ai.ai_provider_ollama.httpx.post",
                return_value=broken_response,
            ),
            pytest.raises(AIProviderUpstreamError),
        ):
            provider._classify_sync(system="sys", user="ping", max_tokens=None, model=None, temperature=None)

    def test_raises_upstream_error_when_the_server_was_never_reachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No network call is even attempted once the server is already known to be down."""
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.get",
            side_effect=httpx.ConnectError("no route to host"),
        ):
            provider = OllamaAIProvider()

        with patch("src.infrastructure.ai.ai_provider_ollama.httpx.post") as mock_post, pytest.raises(AIProviderUpstreamError):
            provider._classify_sync(system="sys", user="ping", max_tokens=None, model=None, temperature=None)

        mock_post.assert_not_called()


class TestProviderIdentity:
    def test_get_provider_name_is_ollama(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _configured_provider(monkeypatch)
        assert provider.get_provider_name() == "ollama"
        assert provider.name == "ollama"


class TestExplainSignal:
    @pytest.mark.asyncio
    async def test_returns_a_clear_message_when_the_server_is_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.get",
            side_effect=httpx.ConnectError("no route to host"),
        ):
            provider = OllamaAIProvider()

        result = await provider.explain_signal("Action: BUY\nConfidence: 70%")

        assert "Ollama" in result
        assert "unavailable" in result.lower() or "not reachable" in result.lower()

    @pytest.mark.asyncio
    async def test_returns_the_model_reply_wrapped_with_a_disclaimer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        provider = _configured_provider(monkeypatch)
        chat_payload = {"message": {"content": "The trend is bullish.\nConclusion: BUY 70% target $100 est"}}

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.post",
            return_value=_fake_response(chat_payload),
        ):
            result = await provider.explain_signal("Action: BUY\nConfidence: 70%", language="en")

        assert "The trend is bullish." in result
        assert "Disclaimer" in result


class TestProviderRegistration:
    """``--provider ollama``-style explicit selection resolves the same way every other name does."""

    def test_ollama_factory_is_registered_and_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider
        from src.infrastructure.ai.ai_provider_registry import _PROVIDER_FACTORIES

        assert "ollama" in _PROVIDER_FACTORIES

        with patch(
            "src.infrastructure.ai.ai_provider_ollama.httpx.get",
            return_value=_fake_response({"version": "0.33.3"}),
        ):
            client = _PROVIDER_FACTORIES["ollama"]()

        assert isinstance(client, OllamaAIProvider)
        assert client.get_provider_name() == "ollama"
