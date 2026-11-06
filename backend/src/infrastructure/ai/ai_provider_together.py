"""
Together.ai AI Provider.

Free tier provider with vision support using Llama 4 Vision.

WHY Together.ai?
- FREE tier (no credit card required)
- Vision support with Llama 4 Scout
- Fast inference
- OpenAI-compatible API

SDK Reference: https://docs.together.ai/docs/quickstart
"""

import asyncio
import logging
from typing import Any

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


class TogetherAIProvider(KeyedAIProviderMixin, VisionAIProvider):
    """
    Together.ai AI provider (FREE tier with vision support).

    WHY Together.ai?
    - FREE tier (no credit card required, unlike Gemini)
    - Vision support with Llama 4 Scout (17B parameters)
    - Fast inference
    - Reliable API

    Cost: FREE tier with generous limits
    Get key from: https://api.together.xyz/settings/api-keys

    SDK: together (official Python SDK)
    Reference: https://docs.together.ai/docs/vision-overview
    """

    _API_KEY_SETTING = "together_api_key"
    _MODEL_SETTING = "ai_model_together"
    _KEY_LABEL = "Together"
    _NOT_CONFIGURED_WARNING = "Together API key not configured. Get free key at api.together.xyz/settings/api-keys"

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize Together.ai client.

        Args:
            api_key: Together API key. If None, uses settings.together_api_key

        Raises:
            ValueError: If API key is empty string
        """
        # BEFORE delegating — see the OpenRouter sibling: `_configure_key_and_model` calls
        # `_init_client`, which may read the vision model.
        self._vision_model = settings.ai_model_together_vision
        self._configure_key_and_model(api_key)

    def _init_client(self) -> None:
        """Initialize Together.ai client."""
        try:
            from together import Together

            # Together SDK uses TOGETHER_API_KEY env var by default,
            # but we pass it explicitly for consistency
            self._client = Together(api_key=self._api_key)
            logger.info(
                "TogetherAIProvider initialized with model: %s, vision: %s",
                self._model,
                self._vision_model,
            )
        except ImportError:
            logger.warning("together package not installed. Run: pip install together")
            self._client = None
        except Exception as e:
            logger.exception("Failed to initialize Together client: %s", e)
            self._client = None

    def is_configured(self) -> bool:
        """Check if Together.ai is configured."""
        return bool(self._api_key and self._client)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "together"

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Generate explanation using Together.ai in the specified language."""
        if not self.is_configured():
            return self._format_response(
                "AI explanation unavailable. Together API key not configured. Get a free key at api.together.xyz/settings/api-keys",
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
            logger.exception("Together API error: %s", e)
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
        """Make synchronous API call to Together.ai."""
        if not self._client:
            return "Together client not initialized."

        language_name = get_language_name(language)

        prompt = f"""{SYSTEM_PROMPT}

Based on the following data, explain why this trading signal was generated:

{context}

IMPORTANT: Respond in {language_name}. Use natural, fluent {language_name}."""

        # Together.ai uses OpenAI-compatible chat completions API.
        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response = self._client.chat.completions.create(**kwargs)

        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
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
        """Lean classification via Together.ai (OpenAI-compatible system + user roles)."""
        if not self._client:
            raise AIProviderUpstreamError(self.get_provider_name())
        response = self._client.chat.completions.create(
            model=model or self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature if temperature is not None else settings.ai_temperature,
            max_tokens=max_tokens if max_tokens is not None else DEFAULT_CLASSIFY_MAX_TOKENS,
        )
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    async def analyze_chart(
        self,
        image_base64: str,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        model_override: str | None = None,  # noqa: ARG002 OpenRouter only
    ) -> str:
        """Analyze chart using Together.ai Vision (Llama 4 Scout) in the specified language."""
        if not self.is_configured():
            return self._format_response("Chart analysis unavailable.", language)

        try:
            response = await asyncio.to_thread(self._call_vision_api, image_base64, context, language)
            return self._format_response(response, language)
        except Exception as e:
            logger.exception("Together Vision error: %s", e)
            return self._format_response("Chart analysis temporarily unavailable.", language)

    def _call_vision_api(self, image_base64: str, context: str, language: str = DEFAULT_LANGUAGE) -> str:
        """
        Make vision API call for chart analysis using Llama 4 Scout.

        Uses centralized, reference-backed chart pattern metrics.
        """
        if not self._client:
            return "Together client not initialized."

        language_name = get_language_name(language)

        system_prompt = build_chart_analysis_reference_system_prompt()

        prompt = f"""{system_prompt}

Analyze this cryptocurrency chart for reference-backed patterns:

{context}

IMPORTANT: Respond in {language_name}. Use natural, fluent {language_name}."""

        # Together.ai vision uses OpenAI-compatible format with base64 images
        # Reference: https://docs.together.ai/docs/vision-overview
        response = self._client.chat.completions.create(
            model=self._vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}",
                            },
                        },
                    ],
                },
            ],
        )

        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return "No analysis generated."
