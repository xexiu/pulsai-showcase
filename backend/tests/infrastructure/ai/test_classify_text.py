"""Behavior tests for the lean ``classify_text`` provider capability (Phase 2).

``classify_text`` is the news-impact path: a short caller-supplied system + user
prompt with NO trading SYSTEM_PROMPT and NO disclaimer (those would 4x tokens and
blow free-tier TPM). These pin that the prompts/overrides reach each SDK verbatim,
that failures map to ``AIProviderUpstreamError`` (so the chain skips), and that the
default (unsupported) provider raises so unknown subclasses degrade gracefully.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.ai import ai_runtime_fallback as runtime_fallback
from src.infrastructure.ai import providers as providers_module
from src.infrastructure.ai.ai_provider_base import (
    DEFAULT_LANGUAGE,
    AIProvider,
    AIProviderUpstreamError,
)
from src.infrastructure.ai.ai_provider_claude import ClaudeAIProvider
from src.infrastructure.ai.ai_provider_gemini import GeminiAIProvider
from src.infrastructure.ai.ai_provider_groq import GroqAIProvider
from src.infrastructure.ai.ai_provider_mock import MockAIProvider
from src.infrastructure.ai.ai_provider_openrouter import OpenRouterAIProvider
from src.infrastructure.ai.ai_provider_together import TogetherAIProvider


class _BareProvider(AIProvider):
    """Minimal AIProvider that does NOT override _classify_sync (default path)."""

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        return ""

    def is_configured(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "bare"


class _FakeOpenAIClient:
    def __init__(self, *, raises: Exception | None = None) -> None:
        self.last_call: dict | None = None
        self._raises = raises
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = MagicMock(side_effect=self._capture)

    def _capture(self, **kwargs: object) -> MagicMock:
        if self._raises is not None:
            raise self._raises
        self.last_call = dict(kwargs)
        choice = MagicMock()
        choice.message = MagicMock(content="VERDICT=BULLISH | CONF=0.80")
        resp = MagicMock()
        resp.choices = [choice]
        return resp


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.last_call: dict | None = None
        self.messages = MagicMock()
        self.messages.create = MagicMock(side_effect=self._capture)

    def _capture(self, **kwargs: object) -> MagicMock:
        self.last_call = dict(kwargs)
        msg = MagicMock()
        msg.content = [MagicMock(text="VERDICT=BEARISH | CONF=0.70")]
        return msg


# ── default (unsupported) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_default_classify_text_marks_provider_unsupported() -> None:
    with pytest.raises(AIProviderUpstreamError):
        await _BareProvider().classify_text(system="s", user="u")


# ── mock (signal-free prod floor) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_classify_text_returns_parseable_neutral() -> None:
    text = await MockAIProvider().classify_text(system="s", user="Headline: x")
    assert "NEUTRAL" in text


# ── groq (OpenAI-style: separate system + user roles) ─────────────────────────


@pytest.mark.asyncio
async def test_groq_classify_text_sends_system_and_user_roles_and_overrides() -> None:
    fake = _FakeOpenAIClient()
    provider = GroqAIProvider.__new__(GroqAIProvider)
    provider._api_key = "k"
    provider._client = fake
    provider._model = "llama-default"

    out = await provider.classify_text(
        system="SYS",
        user="USR",
        max_tokens=24,
        model="llama-override",
        temperature=0.0,
    )

    assert out == "VERDICT=BULLISH | CONF=0.80"
    assert fake.last_call is not None
    assert fake.last_call["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]
    assert fake.last_call["model"] == "llama-override"
    assert fake.last_call["max_tokens"] == 24
    assert fake.last_call["temperature"] == 0.0  # explicit 0.0 honored, not coerced to default


@pytest.mark.asyncio
async def test_groq_classify_text_maps_upstream_failure() -> None:
    fake = _FakeOpenAIClient(raises=ValueError("boom"))
    provider = GroqAIProvider.__new__(GroqAIProvider)
    provider._api_key = "k"
    provider._client = fake
    provider._model = "llama-default"

    with pytest.raises(AIProviderUpstreamError):
        await provider.classify_text(system="s", user="u", max_tokens=24)


# ── openrouter + together (OpenAI-compatible, same shape as groq) ─────────────


@pytest.mark.asyncio
async def test_openrouter_classify_text_sends_roles_and_headers() -> None:
    fake = _FakeOpenAIClient()
    provider = OpenRouterAIProvider.__new__(OpenRouterAIProvider)
    provider._api_key = "k"
    provider._client = fake
    provider._model = "or-default"

    out = await provider.classify_text(system="SYS", user="USR", max_tokens=24, temperature=0.0)

    assert out == "VERDICT=BULLISH | CONF=0.80"
    assert fake.last_call is not None
    assert fake.last_call["messages"][0] == {"role": "system", "content": "SYS"}
    assert "extra_headers" in fake.last_call


@pytest.mark.asyncio
async def test_together_classify_text_sends_roles() -> None:
    fake = _FakeOpenAIClient()
    provider = TogetherAIProvider.__new__(TogetherAIProvider)
    provider._api_key = "k"
    provider._client = fake
    provider._model = "tg-default"

    out = await provider.classify_text(system="SYS", user="USR", max_tokens=24, temperature=0.0)

    assert out == "VERDICT=BULLISH | CONF=0.80"
    assert fake.last_call is not None
    assert fake.last_call["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]


# ── gemini (genai SDK: system_instruction + config) ───────────────────────────


class _FakeGenaiModels:
    def __init__(self) -> None:
        self.last_call: dict | None = None

    def generate_content(self, **kwargs: object) -> MagicMock:
        self.last_call = dict(kwargs)
        resp = MagicMock()
        resp.text = "VERDICT=BEARISH | CONF=0.70"
        return resp


class _FakeGenaiClient:
    def __init__(self) -> None:
        self.models = _FakeGenaiModels()


@pytest.mark.asyncio
async def test_gemini_classify_text_uses_system_instruction_config() -> None:
    fake = _FakeGenaiClient()
    provider = GeminiAIProvider.__new__(GeminiAIProvider)
    provider._api_key = "k"
    provider._client = fake
    provider._model = "gemini-default"

    out = await provider.classify_text(system="SYS", user="USR", max_tokens=24, model="gemini-x", temperature=0.0)

    assert out == "VERDICT=BEARISH | CONF=0.70"
    assert fake.models.last_call is not None
    assert fake.models.last_call["model"] == "gemini-x"
    assert fake.models.last_call["contents"] == "USR"
    # system goes through GenerateContentConfig.system_instruction, not contents.
    assert fake.models.last_call["config"].system_instruction == "SYS"


# ── claude (system param + single user message) ───────────────────────────────


@pytest.mark.asyncio
async def test_claude_classify_text_uses_system_param_and_user_message() -> None:
    fake = _FakeAnthropicClient()
    provider = ClaudeAIProvider.__new__(ClaudeAIProvider)
    provider._api_key = "k"
    provider._client = fake
    provider._model = "claude-default"

    out = await provider.classify_text(system="SYS", user="USR", max_tokens=24, model="claude-x", temperature=0.0)

    assert out == "VERDICT=BEARISH | CONF=0.70"
    assert fake.last_call is not None
    assert fake.last_call["system"] == "SYS"
    assert fake.last_call["messages"] == [{"role": "user", "content": "USR"}]
    assert fake.last_call["model"] == "claude-x"
    assert fake.last_call["max_tokens"] == 24


# ── expected-error detection (rate limits log WARNING, not ERROR tracebacks) ──


class _RateLimitError(Exception):
    """Stand-in whose class name carries the 'RateLimit' marker."""


class _StatusError(Exception):
    def __init__(self) -> None:
        super().__init__("429")
        self.status_code = 429


def test_expected_upstream_error_detection_is_duck_typed() -> None:
    provider = MockAIProvider()
    # By class-name marker (e.g. groq.RateLimitError / anthropic.RateLimitError).
    assert provider._is_expected_upstream_error(_RateLimitError()) is True
    # By transient HTTP status on the exception.
    assert provider._is_expected_upstream_error(_StatusError()) is True
    # A genuine bug is NOT swallowed as "expected" (keeps the full traceback).
    assert provider._is_expected_upstream_error(RuntimeError("real bug")) is False


class _RateLimitedProvider(AIProvider):
    """Provider whose sync classify raises an expected (rate-limit) error."""

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        return ""

    def is_configured(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "rl"

    def _classify_sync(self, *, system: str, user: str, max_tokens: int | None, model: str | None, temperature: float | None) -> str:
        raise _RateLimitError("429")


@pytest.mark.asyncio
async def test_classify_text_maps_expected_error_to_upstream_error() -> None:
    # Expected (rate-limit) errors are caught, logged as WARNING, and surfaced as
    # AIProviderUpstreamError so the chain skips — never leaked raw.
    with pytest.raises(AIProviderUpstreamError):
        await _RateLimitedProvider().classify_text(system="s", user="u")


# ── news-impact fallback chain walker ─────────────────────────────────────────


class _StubProvider(AIProvider):
    def __init__(self, *, configured: bool, text: str = "", raises: bool = False) -> None:
        self._configured = configured
        self._text = text
        self._raises = raises

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        return ""

    def is_configured(self) -> bool:
        return self._configured

    def get_provider_name(self) -> str:
        return "stub"

    async def classify_text(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        if self._raises:
            raise AIProviderUpstreamError("stub")
        return self._text


@pytest.mark.asyncio
async def test_news_fallback_uses_mock_in_mock_mode() -> None:
    # Patched on `ai_runtime_fallback`, the module whose BINDING the chain walker reads.
    # `providers` re-exports the name for its own callers, and patching the re-export left the
    # walker reading the real `get_mock_mode`: this test then walked the live chain and was
    # answered by a LOCAL OLLAMA model in Chinese. A unit test reaching a real LLM is exactly
    # what mock mode exists to prevent, and it was invisible until the modules were separated.
    with patch.object(runtime_fallback, "get_mock_mode", return_value=True):
        out = await providers_module.classify_text_with_news_fallback(system="s", user="u")
    assert out is not None
    assert "NEUTRAL" in out


@pytest.mark.asyncio
async def test_news_fallback_returns_first_configured_success() -> None:
    groq = _StubProvider(configured=True, text="VERDICT=BULLISH | CONF=0.80")
    unconfigured = _StubProvider(configured=False)
    with (
        patch.object(providers_module, "get_mock_mode", return_value=False),
        # openrouter precedes groq in the chain — stub it unconfigured so the test is hermetic
        # (independent of whether a real OPENROUTER_API_KEY is present in the local .env).
        patch.dict(
            runtime_fallback._PROVIDER_FACTORIES,
            {"openrouter": lambda: unconfigured, "groq": lambda: groq},
        ),
    ):
        out = await providers_module.classify_text_with_news_fallback(system="s", user="u")
    assert out == "VERDICT=BULLISH | CONF=0.80"


@pytest.mark.asyncio
async def test_news_fallback_skips_failed_provider_down_to_mock() -> None:
    failing = _StubProvider(configured=True, raises=True)
    unconfigured = _StubProvider(configured=False)
    with (
        patch.object(providers_module, "get_mock_mode", return_value=False),
        # Stub every real upstream unconfigured so the chain deterministically walks
        # groq(fail) → mock, regardless of which provider keys the local .env has set.
        patch.dict(
            runtime_fallback._PROVIDER_FACTORIES,
            {
                "openrouter": lambda: unconfigured,
                "together": lambda: unconfigured,
                "gemini": lambda: unconfigured,
                "groq": lambda: failing,
            },
        ),
    ):
        out = await providers_module.classify_text_with_news_fallback(system="s", user="u")
    # groq raised → chain walks to mock (always configured) → NEUTRAL floor.
    assert out is not None
    assert "NEUTRAL" in out


class _CapturingProvider(AIProvider):
    """Records the ``model`` arg classify_text received, for news-impact routing assertions."""

    def __init__(self, *, configured: bool = True, raises: bool = False) -> None:
        self._configured = configured
        self._raises = raises
        self.model_arg: str | None = "__unset__"

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        return ""

    def is_configured(self) -> bool:
        return self._configured

    def get_provider_name(self) -> str:
        return "capture"

    async def classify_text(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        self.model_arg = model
        if self._raises:
            raise AIProviderUpstreamError("capture")
        return "VERDICT=NEUTRAL | CONF=0.00"


@pytest.mark.asyncio
async def test_news_fallback_routes_news_impact_model_to_openrouter() -> None:
    """The validated DeepSeek model (settings.ai_model_news_impact) must reach the OpenRouter slot."""
    openrouter = _CapturingProvider(configured=True)
    with (
        patch.object(providers_module, "get_mock_mode", return_value=False),
        patch.dict(runtime_fallback._PROVIDER_FACTORIES, {"openrouter": lambda: openrouter}),
    ):
        out = await providers_module.classify_text_with_news_fallback(system="s", user="u")
    assert out == "VERDICT=NEUTRAL | CONF=0.00"
    assert openrouter.model_arg == providers_module.settings.ai_model_news_impact


@pytest.mark.asyncio
async def test_news_fallback_uses_provider_default_for_non_openrouter() -> None:
    """Non-OpenRouter providers keep model=None — a deepseek/* slug is meaningless to them."""
    openrouter = _CapturingProvider(configured=True, raises=True)  # fails → chain advances to groq
    groq = _CapturingProvider(configured=True)
    with (
        patch.object(providers_module, "get_mock_mode", return_value=False),
        patch.dict(
            runtime_fallback._PROVIDER_FACTORIES,
            {"openrouter": lambda: openrouter, "groq": lambda: groq},
        ),
    ):
        out = await providers_module.classify_text_with_news_fallback(system="s", user="u")
    assert out == "VERDICT=NEUTRAL | CONF=0.00"
    assert openrouter.model_arg == providers_module.settings.ai_model_news_impact  # got DeepSeek, then failed
    assert groq.model_arg is None  # fell through to groq with its own default model


class _Credit402Error(Exception):
    """Stand-in for an OpenAI/OpenRouter 402 (credits/quota exhausted) upstream error."""

    status_code = 402


class _Raises402Provider(_BareProvider):
    """Bare provider whose classification call hits a 402 — exercises the base error mapper."""

    def _classify_sync(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        raise _Credit402Error("insufficient credits")


@pytest.mark.asyncio
async def test_classify_text_logs_402_credits_as_warning_not_error(caplog: pytest.LogCaptureFixture) -> None:
    """A 402 (credits exhausted) is a handled, recurring fallback condition → WARNING, not ERROR spam.

    Functionally it must still map to AIProviderUpstreamError so the chain degrades to FinBERT;
    the assertion here pins the log LEVEL so a dry prod key does not flood ERROR tracebacks.
    """
    with (
        caplog.at_level(logging.WARNING, logger="src.infrastructure.ai.ai_provider_base"),
        pytest.raises(AIProviderUpstreamError),
    ):
        await _Raises402Provider().classify_text(system="s", user="u")
    assert any(r.levelname == "WARNING" for r in caplog.records)
    assert not any(r.levelname == "ERROR" for r in caplog.records)
