"""
TDD Tests for AI Provider Module Extraction.

Tests written FIRST before extraction.
Following .cursorrules TDD requirements.

Tests verify:
- All providers importable from new modules
- Backward compatibility from providers.py
- Provider behavior preserved after extraction
"""

from __future__ import annotations

import pytest


class TestLanguageConfiguration:
    """
    TDD tests for configurable language settings.

    WHY: Both DEFAULT_LANGUAGE and SUPPORTED_LANGUAGES should be configurable
    via settings, not hardcoded. This allows different deployments to:
    - Target different markets (Spanish for LATAM, English for US, etc.)
    - Enable/disable languages without code changes
    """

    # =========================================================================
    # DEFAULT_LANGUAGE Tests
    # =========================================================================

    def test_default_language_comes_from_settings(self) -> None:
        """DEFAULT_LANGUAGE should be loaded from settings.ai_default_language."""
        from src.infrastructure.ai.ai_provider_base import DEFAULT_LANGUAGE
        from src.infrastructure.config.settings import settings

        # DEFAULT_LANGUAGE should match settings value
        assert settings.ai_default_language == DEFAULT_LANGUAGE

    def test_settings_has_ai_default_language(self) -> None:
        """Settings should have ai_default_language field."""
        from src.infrastructure.config.settings import settings

        # Settings must have the field
        assert hasattr(settings, "ai_default_language")
        # Should be a string
        assert isinstance(settings.ai_default_language, str)
        # Should be a valid language code (2 chars like ISO 639-1)
        assert len(settings.ai_default_language) == 2

    def test_default_language_is_valid_code(self) -> None:
        """Default language must be in SUPPORTED_LANGUAGES."""
        from src.infrastructure.ai.ai_provider_base import (
            DEFAULT_LANGUAGE,
            SUPPORTED_LANGUAGES,
        )

        assert SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE]

    # =========================================================================
    # SUPPORTED_LANGUAGES Tests
    # =========================================================================

    def test_supported_languages_comes_from_settings(self) -> None:
        """SUPPORTED_LANGUAGES keys should match settings.ai_supported_languages_list."""
        from src.infrastructure.ai.ai_provider_base import SUPPORTED_LANGUAGES
        from src.infrastructure.config.settings import settings

        # SUPPORTED_LANGUAGES keys should match configured codes
        assert set(SUPPORTED_LANGUAGES.keys()) == set(settings.ai_supported_languages_list)

    def test_settings_has_ai_supported_languages(self) -> None:
        """Settings should have ai_supported_languages field."""
        from src.infrastructure.config.settings import settings

        # Settings must have the field (comma-separated string)
        assert hasattr(settings, "ai_supported_languages")
        assert isinstance(settings.ai_supported_languages, str)

        # And the computed list property
        assert hasattr(settings, "ai_supported_languages_list")
        assert isinstance(settings.ai_supported_languages_list, list)
        assert len(settings.ai_supported_languages_list) > 0

    def test_supported_languages_has_full_names(self) -> None:
        """SUPPORTED_LANGUAGES should map codes to full language names."""
        from src.infrastructure.ai.ai_provider_base import SUPPORTED_LANGUAGES

        # Each entry should have code -> full name
        for code, name in SUPPORTED_LANGUAGES.items():
            assert len(code) == 2  # ISO 639-1
            assert len(name) > 2  # Full name like "Spanish", not "es"
            assert name[0].isupper()  # Capitalized

    def test_language_names_mapping_exists(self) -> None:
        """LANGUAGE_NAMES constant should exist for code->name lookup."""
        from src.infrastructure.ai.ai_provider_base import LANGUAGE_NAMES

        # Should have common languages
        assert "es" in LANGUAGE_NAMES
        assert "en" in LANGUAGE_NAMES
        assert LANGUAGE_NAMES["es"] == "Spanish"
        assert LANGUAGE_NAMES["en"] == "English"


class TestAIProviderBaseImport:
    """Verify AIProvider base class importable from new module."""

    def test_ai_provider_importable(self) -> None:
        """AIProvider ABC should be importable from ai_provider_base."""
        # Should be abstract
        from abc import ABC

        from src.infrastructure.ai.ai_provider_base import AIProvider

        assert issubclass(AIProvider, ABC)

    def test_constants_importable(self) -> None:
        """Constants should be importable from ai_provider_base."""
        from src.infrastructure.ai.ai_provider_base import (
            DEFAULT_LANGUAGE,
            DISCLAIMERS,
            SUPPORTED_LANGUAGES,
            SYSTEM_PROMPT,
            get_language_name,
        )

        assert "es" in SUPPORTED_LANGUAGES
        assert DEFAULT_LANGUAGE == "es"
        assert "en" in DISCLAIMERS
        assert len(SYSTEM_PROMPT) > 0
        assert get_language_name("en") == "English"

    def test_system_prompt_does_not_expose_model_family_names(self) -> None:
        """User-facing explain system prompt should use generic ML wording."""
        from src.infrastructure.ai.ai_provider_base import SYSTEM_PROMPT

        assert "xgboost" not in SYSTEM_PROMPT.lower()
        assert "ML" in SYSTEM_PROMPT


class TestMockProviderImport:
    """Verify MockAIProvider importable from new module."""

    def test_mock_provider_importable(self) -> None:
        """MockAIProvider should be importable from ai_provider_mock."""
        from src.infrastructure.ai.ai_provider_mock import MockAIProvider

        provider = MockAIProvider()
        assert provider.name == "mock"

    def test_mock_provider_has_explain_signal(self) -> None:
        """MockAIProvider should have explain_signal method."""
        from src.infrastructure.ai.ai_provider_mock import MockAIProvider

        provider = MockAIProvider()
        # Check method exists
        assert hasattr(provider, "explain_signal")
        assert callable(provider.explain_signal)


class TestGroqProviderImport:
    """Verify GroqAIProvider importable from new module."""

    def test_groq_provider_importable(self) -> None:
        """GroqAIProvider should be importable from ai_provider_groq."""
        from src.infrastructure.ai.ai_provider_groq import GroqAIProvider

        # Need API key to instantiate - just check class exists
        assert GroqAIProvider is not None

    def test_groq_provider_requires_api_key(self) -> None:
        """GroqAIProvider should require API key."""
        from src.infrastructure.ai.ai_provider_groq import GroqAIProvider

        with pytest.raises(ValueError, match="API key"):
            GroqAIProvider(api_key="")


class TestClaudeProviderImport:
    """Verify ClaudeAIProvider importable from new module."""

    def test_claude_provider_importable(self) -> None:
        """ClaudeAIProvider should be importable from ai_provider_claude."""
        from src.infrastructure.ai.ai_provider_claude import ClaudeAIProvider

        assert ClaudeAIProvider is not None

    def test_claude_provider_requires_api_key(self) -> None:
        """ClaudeAIProvider should require API key."""
        from src.infrastructure.ai.ai_provider_claude import ClaudeAIProvider

        with pytest.raises(ValueError, match="API key"):
            ClaudeAIProvider(api_key="")


class TestGeminiProviderImport:
    """Verify GeminiAIProvider importable from new module."""

    def test_gemini_provider_importable(self) -> None:
        """GeminiAIProvider should be importable from ai_provider_gemini."""
        from src.infrastructure.ai.ai_provider_gemini import GeminiAIProvider

        assert GeminiAIProvider is not None

    def test_gemini_provider_requires_api_key(self) -> None:
        """GeminiAIProvider should require API key."""
        from src.infrastructure.ai.ai_provider_gemini import GeminiAIProvider

        with pytest.raises(ValueError, match="API key"):
            GeminiAIProvider(api_key="")


class TestBackwardCompatibilityImport:
    """Verify backward compatibility - providers.py re-exports work."""

    def test_all_providers_from_providers_module(self) -> None:
        """All providers should still be importable from providers.py."""
        from src.infrastructure.ai.providers import (
            ClaudeAIProvider,
            GeminiAIProvider,
            GroqAIProvider,
            MockAIProvider,
        )

        # Verify all imported successfully
        assert MockAIProvider().name == "mock"
        # Others require API keys, just check class exists
        assert GroqAIProvider is not None
        assert ClaudeAIProvider is not None
        assert GeminiAIProvider is not None

    def test_factory_functions_from_providers_module(self) -> None:
        """Factory functions should remain in providers.py."""
        from src.infrastructure.ai.providers import (
            get_ai_client,
            get_mock_mode,
            set_mock_mode,
        )

        # Set mock mode and verify
        set_mock_mode(True)
        assert get_mock_mode() is True

        # Get client in mock mode
        client = get_ai_client()
        assert client.name == "mock"

        # Reset
        set_mock_mode(False)

    def test_constants_from_providers_module(self) -> None:
        """Constants should still be importable from providers.py."""
        from src.infrastructure.ai.providers import (
            DEFAULT_LANGUAGE,
            DISCLAIMER,
            DISCLAIMERS,
            LANGUAGE_NAMES,
            SUPPORTED_LANGUAGES,
            SYSTEM_PROMPT,
            get_language_name,
        )

        # All should be importable
        assert DEFAULT_LANGUAGE is not None
        assert DISCLAIMER is not None
        assert DISCLAIMERS is not None
        assert LANGUAGE_NAMES is not None
        assert SUPPORTED_LANGUAGES is not None
        assert SYSTEM_PROMPT is not None
        assert callable(get_language_name)
        assert get_language_name("es") == "Spanish"


class TestMockProviderBehavior:
    """Verify MockAIProvider behavior preserved."""

    @pytest.mark.asyncio
    async def test_explain_signal_returns_string(self) -> None:
        """explain_signal should return explanation string."""
        from src.infrastructure.ai.ai_provider_mock import MockAIProvider

        provider = MockAIProvider()
        # MockAIProvider parses context string for "Action: BUY" pattern
        context = """
        Symbol: BTC/USDT
        Timeframe: 1h
        Action: BUY
        Confidence: 75%
        """

        result = await provider.explain_signal(context)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "BUY" in result

    @pytest.mark.asyncio
    async def test_explain_signal_includes_disclaimer(self) -> None:
        """explain_signal should include disclaimer."""
        from src.infrastructure.ai.ai_provider_mock import MockAIProvider

        provider = MockAIProvider()
        context = {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "action": "SELL",
            "confidence": 60,
        }

        result = await provider.explain_signal(str(context), language="en")

        assert "Disclaimer" in result or "disclaimer" in result.lower()

    @pytest.mark.asyncio
    async def test_explain_signal_respects_language(self) -> None:
        """explain_signal should use specified language disclaimer."""
        from src.infrastructure.ai.ai_provider_mock import MockAIProvider

        provider = MockAIProvider()
        context = {
            "symbol": "ETH/USDT",
            "timeframe": "4h",
            "action": "HOLD",
            "confidence": 50,
        }

        # Spanish
        result_es = await provider.explain_signal(str(context), language="es")
        assert "Aviso" in result_es  # Spanish disclaimer

        # English
        result_en = await provider.explain_signal(str(context), language="en")
        assert "Disclaimer" in result_en  # English disclaimer


class TestOutboundAiCallsAreTimeBounded:
    """An LLM call with no deadline is a silent hang, not a slow call.

    MEASURED 2026-09-10, and this is the incident that produced the test. The 4h
    `llm_market_decision` band run sat for **4h47m wall clock on 6.3s of CPU**, stuck at
    `125/421 decided`, its log untouched for 61 minutes, holding one ESTABLISHED TCP socket to
    Cloudflare (which fronts Groq). Nothing was computing and nothing timed out.

    The retry loop added the day before is what armed it. Before, a 429 raised `RateLimitError`
    and killed the run LOUDLY. After, a 429 backs off and retries — correct — but no call is
    bounded, so one stalled read waits forever and the run neither finishes nor fails. That is
    exactly ARCHITECTURE_PATTERNS.md section 5's honesty clause: "a resilience pattern without
    observability is worse than none. It converts a loud failure into a silent degradation."

    The fix belongs in the PROVIDER, not the research harness, because prod calls the same client.
    """

    def test_groq_client_is_constructed_with_an_explicit_timeout(self) -> None:
        """The SDK default is not a decision. An explicit deadline is."""
        import sys

        import src.infrastructure.ai.ai_provider_groq as groq_module
        from src.shared.constants.ai_provider_http import AI_PROVIDER_REQUEST_TIMEOUT_SECONDS

        captured: dict[str, object] = {}

        class _FakeGroq:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)

        fake_sdk = type("_FakeSdkModule", (), {"Groq": _FakeGroq})

        original = sys.modules.get("groq")
        sys.modules["groq"] = fake_sdk  # type: ignore[assignment]
        try:
            provider = groq_module.GroqAIProvider.__new__(groq_module.GroqAIProvider)
            provider._api_key = "test-key"
            provider._model = "test-model"
            provider._init_client()
        finally:
            if original is None:
                sys.modules.pop("groq", None)
            else:
                sys.modules["groq"] = original

        assert "timeout" in captured, (
            "Groq() was constructed without a timeout; a stalled read then hangs forever — measured at 4h47m on 6.3s of CPU before this test existed."
        )
        assert captured["timeout"] == AI_PROVIDER_REQUEST_TIMEOUT_SECONDS

    def test_the_timeout_constant_is_a_usable_deadline(self) -> None:
        """Bounded on both sides: long enough for a reasoning model, short enough to notice."""
        from src.shared.constants.ai_provider_http import AI_PROVIDER_REQUEST_TIMEOUT_SECONDS

        assert 10.0 <= AI_PROVIDER_REQUEST_TIMEOUT_SECONDS <= 300.0
