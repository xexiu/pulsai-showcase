"""Behavior pin: admin numeric overrides reach the provider call.

We mock the AnthropicSDK Messages.create() call and verify that `temperature`
and `model` propagate from `explain_signal_with_runtime_fallback`'s kwargs all
the way down to the SDK invocation.

Why this test exists: without it, a future refactor could silently drop the
per-call params (the old behavior) and admin temperature/model overrides would
become no-ops without breaking any other test.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.ai.ai_provider_claude import ClaudeAIProvider
from src.infrastructure.ai.ai_provider_groq import GroqAIProvider
from src.infrastructure.ai.ai_provider_mock import MockAIProvider


class _FakeAnthropicMessage:
    def __init__(self, text: str = "ok") -> None:
        self.content = [MagicMock(text=text)]


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.last_call: dict | None = None
        self.messages = MagicMock()
        self.messages.create = MagicMock(side_effect=self._capture)

    def _capture(self, **kwargs: object) -> _FakeAnthropicMessage:
        self.last_call = dict(kwargs)
        return _FakeAnthropicMessage("explanation body")


@pytest.mark.asyncio
async def test_claude_provider_forwards_temperature_and_model_overrides() -> None:
    fake_client = _FakeAnthropicClient()
    provider = ClaudeAIProvider.__new__(ClaudeAIProvider)
    provider._api_key = "test-key"
    provider._client = fake_client
    provider._model = "claude-sonnet-4-6"  # registry default

    await provider.explain_signal(
        "## ctx",
        language="en",
        temperature=0.9,
        model="claude-opus-4-7",
    )

    assert fake_client.last_call is not None
    assert fake_client.last_call["temperature"] == 0.9
    assert fake_client.last_call["model"] == "claude-opus-4-7"


@pytest.mark.asyncio
async def test_claude_provider_uses_defaults_when_overrides_omitted() -> None:
    fake_client = _FakeAnthropicClient()
    provider = ClaudeAIProvider.__new__(ClaudeAIProvider)
    provider._api_key = "test-key"
    provider._client = fake_client
    provider._model = "claude-sonnet-4-6"

    await provider.explain_signal("## ctx", language="en")

    assert fake_client.last_call is not None
    assert fake_client.last_call["model"] == "claude-sonnet-4-6"
    # temperature falls back to settings default (0.3) — must be a real float.
    assert isinstance(fake_client.last_call["temperature"], float)


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.last_call: dict | None = None
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = MagicMock(side_effect=self._capture)

    def _capture(self, **kwargs: object) -> MagicMock:
        self.last_call = dict(kwargs)
        choice = MagicMock()
        choice.message = MagicMock(content="hello")
        resp = MagicMock()
        resp.choices = [choice]
        return resp


@pytest.mark.asyncio
async def test_groq_provider_forwards_temperature_and_model_overrides() -> None:
    fake_client = _FakeOpenAIClient()
    provider = GroqAIProvider.__new__(GroqAIProvider)
    provider._api_key = "test-key"
    provider._client = fake_client
    provider._model = "llama-3.3-70b-versatile"

    await provider.explain_signal(
        "## ctx",
        language="en",
        temperature=0.05,
        max_tokens=512,
        model="llama-override",
    )

    assert fake_client.last_call is not None
    assert fake_client.last_call["temperature"] == 0.05
    assert fake_client.last_call["max_tokens"] == 512
    assert fake_client.last_call["model"] == "llama-override"


@pytest.mark.asyncio
async def test_mock_provider_silently_ignores_overrides() -> None:
    # Mock ignores numeric overrides (no real LLM); call must still succeed.
    provider = MockAIProvider()
    text = await provider.explain_signal(
        "Action: BUY\nConfidence: 80%",
        language="en",
        temperature=0.7,
        max_tokens=999,
        model="anything",
    )
    assert isinstance(text, str)
    assert text  # disclaimer always appended


@pytest.mark.asyncio
async def test_runtime_fallback_forwards_overrides_to_chosen_provider() -> None:
    """End-to-end: admin override reaches the actual provider serving the request."""
    from src.infrastructure.ai import ai_runtime_fallback as runtime_fallback
    from src.infrastructure.ai import providers as providers_module

    fake_client = _FakeAnthropicClient()
    fake_provider = ClaudeAIProvider.__new__(ClaudeAIProvider)
    fake_provider._api_key = "test-key"
    fake_provider._client = fake_client
    fake_provider._model = "claude-sonnet-4-6"

    with (
        # Patched on the module whose BINDING the chain walker reads. `providers` re-exports the
        # name for callers; patching the re-export left `ai_runtime_fallback` reading the real
        # one, and the classify test that made the same mistake reached a LIVE Ollama instead of
        # the mock -- a unit test talking to a local model, which is how the split found it.
        patch.object(runtime_fallback, "get_mock_mode", return_value=False),
        patch.dict(
            runtime_fallback._PROVIDER_FACTORIES,
            {"claude": lambda: fake_provider},
        ),
    ):
        text, name = await providers_module.explain_signal_with_runtime_fallback(
            user=None,  # FREE chain doesn't start with claude; force PRO by overriding
            context="## ctx",
            language="en",
            temperature=0.42,
            model="claude-opus-4-7",
        )
        # FREE chain doesn't include claude; the test asserts forwarding works
        # when claude IS chosen — exercise via the PRO chain explicitly:
        from src.domain.enums import SubscriptionTier

        class _U:
            subscription_tier = SubscriptionTier.PRO

        text, name = await providers_module.explain_signal_with_runtime_fallback(
            user=_U(),  # type: ignore[arg-type]
            context="## ctx",
            language="en",
            temperature=0.42,
            model="claude-opus-4-7",
        )

    assert name == "claude"
    assert isinstance(text, str)
    assert fake_client.last_call is not None
    assert fake_client.last_call["temperature"] == 0.42
    assert fake_client.last_call["model"] == "claude-opus-4-7"
