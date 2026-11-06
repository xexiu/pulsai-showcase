"""
Claude AI Provider.

Premium quality provider with vision support.

Extracted from providers.py for modularity.
"""

import asyncio
import logging

from src.infrastructure.ai.ai_provider_base import (
    DEFAULT_CLASSIFY_MAX_TOKENS,
    DEFAULT_LANGUAGE,
    SYSTEM_PROMPT,
    AIProviderUpstreamError,
    VisionAIProvider,
    get_language_name,
)
from src.infrastructure.ai.ai_provider_keyed import KeyedAIProviderMixin
from src.infrastructure.config.settings import settings
from src.shared.chart_pattern_reference_stats import (
    build_chart_analysis_reference_system_prompt,
)

logger = logging.getLogger(__name__)


class ClaudeAIProvider(KeyedAIProviderMixin, VisionAIProvider):
    """
    Anthropic Claude AI provider (paid).

    WHY Claude?
    - Highest quality responses
    - Vision support for chart analysis
    - Best at following complex instructions

    Cost: ~$3-15 per 1M tokens (depends on model)
    """

    _API_KEY_SETTING = "anthropic_api_key"
    _MODEL_SETTING = "ai_model_claude"
    _KEY_LABEL = "Anthropic"
    _NOT_CONFIGURED_WARNING = "Anthropic API key not configured"

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key. If None, uses settings.anthropic_api_key

        Raises:
            ValueError: If API key is empty string
        """
        self._configure_key_and_model(api_key)

    def _init_client(self) -> None:
        """Initialize Anthropic client."""
        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
            logger.info("ClaudeAIProvider initialized with model: %s", self._model)
        except ImportError:
            logger.warning("anthropic package not installed")
            self._client = None
        except Exception as e:
            logger.exception("Failed to initialize Claude client: %s", e)
            self._client = None

    def is_configured(self) -> bool:
        """Check if Claude is configured."""
        return bool(self._api_key and self._client)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "claude"

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Generate explanation using Claude in the specified language."""
        if not self.is_configured():
            return self._format_response(
                "AI explanation unavailable. Anthropic API key not configured.",
                language,
            )

        try:
            response = await asyncio.to_thread(
                self._call_api,
                context,
                language,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
            return self._format_response(response, language)
        except Exception as e:
            logger.exception("Claude API error: %s", e)
            raise AIProviderUpstreamError(self.get_provider_name()) from e

    def _call_api(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Make synchronous API call to Claude."""
        if not self._client:
            return "Claude client not initialized."

        language_name = get_language_name(language)

        message = self._client.messages.create(
            model=model or self._model,
            max_tokens=max_tokens or 2000,
            temperature=temperature if temperature is not None else settings.ai_temperature,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Based on the following data, explain why this trading signal was generated:\n\n"
                        f"{context}\n\n"
                        f"IMPORTANT: Respond in {language_name}. Use natural, fluent {language_name}."
                    ),
                }
            ],
        )

        if message.content:
            result: str = message.content[0].text
            return result
        return "No explanation generated."

    def _classify_sync(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None,
        model: str | None,
        temperature: float | None,
    ) -> str:
        """Lean classification via Claude (system param + single user message)."""
        if not self._client:
            raise AIProviderUpstreamError(self.get_provider_name())
        message = self._client.messages.create(
            model=model or self._model,
            max_tokens=max_tokens if max_tokens is not None else DEFAULT_CLASSIFY_MAX_TOKENS,
            temperature=temperature if temperature is not None else settings.ai_temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if message.content:
            result: str = message.content[0].text
            return result
        return ""

    async def analyze_chart(
        self,
        image_base64: str,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        model_override: str | None = None,  # noqa: ARG002 OpenRouter only
    ) -> str:
        """Analyze chart using Claude Vision in the specified language."""
        if not self.is_configured():
            return self._format_response("Chart analysis unavailable.", language)

        try:
            response = await asyncio.to_thread(self._call_vision_api, image_base64, context, language)
            return self._format_response(response, language)
        except Exception as e:
            logger.exception("Claude Vision error: %s", e)
            return self._format_response("Chart analysis temporarily unavailable.", language)

    def _call_vision_api(self, image_base64: str, context: str, language: str = DEFAULT_LANGUAGE) -> str:
        """
        Make vision API call for chart analysis.

        Uses centralized, reference-backed chart pattern metrics.
        """
        if not self._client:
            return "Claude client not initialized."

        language_name = get_language_name(language)

        system_prompt = build_chart_analysis_reference_system_prompt()

        message = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            temperature=settings.ai_temperature,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f"Analyze this cryptocurrency chart for reference-backed patterns:\n\n"
                                f"{context}\n\n"
                                f"IMPORTANT: Respond in {language_name}. Use natural, fluent {language_name}."
                            ),
                        },
                    ],
                }
            ],
        )

        if message.content:
            result: str = message.content[0].text
            return result
        return "No analysis generated."
