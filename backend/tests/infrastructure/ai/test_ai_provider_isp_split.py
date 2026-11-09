"""
Behavior tests for AIProvider ISP split (Interface Segregation Principle).

WHY SPLIT:
- Groq doesn't support vision but was forced to implement analyze_chart
- ISP says clients should not depend on interfaces they don't use
- VisionAIProvider extends AIProvider for providers with chart analysis

TDD: Written BEFORE the split implementation.
"""

from __future__ import annotations

import pytest


class TestVisionAIProviderExists:
    """VisionAIProvider should be a separate class extending AIProvider."""

    def test_vision_provider_importable(self) -> None:
        from src.infrastructure.ai.ai_provider_base import VisionAIProvider

        assert VisionAIProvider is not None

    def test_vision_provider_extends_ai_provider(self) -> None:
        from src.infrastructure.ai.ai_provider_base import AIProvider, VisionAIProvider

        assert issubclass(VisionAIProvider, AIProvider)

    def test_vision_provider_has_analyze_chart(self) -> None:
        from src.infrastructure.ai.ai_provider_base import VisionAIProvider

        assert hasattr(VisionAIProvider, "analyze_chart")

    def test_ai_provider_no_longer_requires_analyze_chart(self) -> None:
        """AIProvider base should NOT force analyze_chart on text-only providers."""
        from src.infrastructure.ai.ai_provider_base import AIProvider

        abstract_methods = getattr(AIProvider, "__abstractmethods__", frozenset())
        assert "analyze_chart" not in abstract_methods


class TestSupportsVisionProperty:
    """providers should expose supports_vision for consumer checks."""

    def test_vision_providers_support_vision(self) -> None:
        from src.infrastructure.ai.ai_provider_base import VisionAIProvider
        from src.infrastructure.ai.ai_provider_mock import MockAIProvider

        provider = MockAIProvider()
        assert isinstance(provider, VisionAIProvider)
        assert provider.supports_vision is True

    def test_text_only_providers_do_not_support_vision(self) -> None:
        """Groq should NOT be a VisionAIProvider."""
        from src.infrastructure.ai.ai_provider_base import VisionAIProvider
        from src.infrastructure.ai.ai_provider_groq import GroqAIProvider

        assert not issubclass(GroqAIProvider, VisionAIProvider)

    def test_groq_supports_vision_is_false(self) -> None:
        """Groq.supports_vision should return False."""
        from src.infrastructure.ai.ai_provider_groq import GroqAIProvider

        provider = GroqAIProvider(api_key="test-key")
        assert provider.supports_vision is False


class TestVisionProviderClassHierarchy:
    """Concrete providers must be in the correct hierarchy."""

    @pytest.mark.parametrize(
        ("module_path", "class_name"),
        [
            ("src.infrastructure.ai.ai_provider_claude", "ClaudeAIProvider"),
            ("src.infrastructure.ai.ai_provider_gemini", "GeminiAIProvider"),
            ("src.infrastructure.ai.ai_provider_together", "TogetherAIProvider"),
            ("src.infrastructure.ai.ai_provider_openrouter", "OpenRouterAIProvider"),
            ("src.infrastructure.ai.ai_provider_mock", "MockAIProvider"),
        ],
    )
    def test_vision_capable_provider_extends_vision_base(
        self,
        module_path: str,
        class_name: str,
    ) -> None:
        """All vision-capable providers must extend VisionAIProvider."""
        import importlib

        from src.infrastructure.ai.ai_provider_base import VisionAIProvider

        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        assert issubclass(cls, VisionAIProvider), f"{class_name} should extend VisionAIProvider"


class TestGroqNoLongerHasDummyAnalyzeChart:
    """After ISP split, Groq should NOT have a local analyze_chart method."""

    def test_groq_does_not_define_analyze_chart(self) -> None:
        """Groq's own class dict should NOT contain analyze_chart."""
        from src.infrastructure.ai.ai_provider_groq import GroqAIProvider

        own_methods = set(GroqAIProvider.__dict__.keys())
        assert "analyze_chart" not in own_methods


class TestBackwardCompatProviderExports:
    """providers.py should export VisionAIProvider alongside existing exports."""

    def test_vision_provider_exported_from_providers(self) -> None:
        from src.infrastructure.ai.providers import VisionAIProvider

        assert VisionAIProvider is not None

    def test_existing_exports_still_work(self) -> None:
        from src.infrastructure.ai.providers import (
            AIProvider,
            ClaudeAIProvider,
            GeminiAIProvider,
            GroqAIProvider,
            MockAIProvider,
            OpenRouterAIProvider,
            TogetherAIProvider,
        )

        assert AIProvider is not None
        assert ClaudeAIProvider is not None
        assert GeminiAIProvider is not None
        assert GroqAIProvider is not None
        assert MockAIProvider is not None
        assert OpenRouterAIProvider is not None
        assert TogetherAIProvider is not None


class TestMockVisionBehavior:
    """Mock provider should still support analyze_chart as a VisionAIProvider."""

    @pytest.mark.asyncio
    async def test_mock_analyze_chart_returns_string(self) -> None:
        from src.infrastructure.ai.ai_provider_mock import MockAIProvider

        provider = MockAIProvider()
        result = await provider.analyze_chart(
            image_base64="base64data",
            context="BTC/USDT 1h",
        )
        assert isinstance(result, str)
        assert len(result) > 0
