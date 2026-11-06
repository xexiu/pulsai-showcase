"""
Gemini AI Provider.

Free tier provider with vision support.

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


class GeminiAIProvider(KeyedAIProviderMixin, VisionAIProvider):
    """
    Google Gemini AI provider (FREE tier with vision support).

    WHY Gemini?
    - FREE tier (15 RPM, 1M tokens/month)
    - Vision support for chart analysis
    - Fast inference (Gemini 2.0 Flash)

    Cost: FREE tier sufficient for development/testing
    Get key from: https://aistudio.google.com/app/apikey

    SDK: google-genai (NEW unified SDK, migrated from google-generativeai)
    Reference: https://ai.google.dev/gemini-api/docs/migrate
    """

    _API_KEY_SETTING = "gemini_api_key"
    _MODEL_SETTING = "ai_model_gemini"
    _KEY_LABEL = "Gemini"
    _NOT_CONFIGURED_WARNING = "Gemini API key not configured. Get free key at aistudio.google.com"

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key. If None, uses settings.gemini_api_key

        Raises:
            ValueError: If API key is empty string
        """
        self._configure_key_and_model(api_key)

    def _init_client(self) -> None:
        """Initialize Gemini client using NEW google-genai SDK."""
        try:
            from google import genai

            # NEW SDK: Create centralized Client object
            self._client = genai.Client(api_key=self._api_key)
            logger.info("GeminiAIProvider initialized with model: %s (google-genai SDK)", self._model)
        except ImportError:
            logger.warning("google-genai package not installed. Run: pip install google-genai")
            self._client = None
        except Exception as e:
            logger.exception("Failed to initialize Gemini client: %s", e)
            self._client = None

    def is_configured(self) -> bool:
        """Check if Gemini is configured."""
        return bool(self._api_key and self._client)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "gemini"

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Generate explanation using Gemini in the specified language."""
        if not self.is_configured():
            return self._format_response(
                "AI explanation unavailable. Gemini API key not configured. Get a free key at aistudio.google.com",
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
            logger.exception("Gemini API error: %s", e)
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
        """Make synchronous API call to Gemini using NEW SDK.

        Per-call temperature/max_tokens not threaded into the Gemini SDK here —
        the NEW SDK accepts `config=GenerateContentConfig(...)` but adding it
        would require importing the type and is best done in a follow-up PR.
        Model override is honored; temperature/max_tokens fall through to env.
        """
        if not self._client:
            return "Gemini client not initialized."

        # Mark intentionally-unused per-call params (see docstring).
        _ = temperature, max_tokens

        language_name = get_language_name(language)

        prompt = f"""{SYSTEM_PROMPT}

Based on the following data, explain why this trading signal was generated:

{context}

IMPORTANT: Respond in {language_name}. Use natural, fluent {language_name}."""

        # NEW SDK: Use client.models.generate_content()
        response = self._client.models.generate_content(
            model=model or self._model,
            contents=prompt,
        )

        if response.text:
            return str(response.text)
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
        """Lean classification via Gemini (system_instruction + config; honors temp/cap)."""
        if not self._client:
            raise AIProviderUpstreamError(self.get_provider_name())
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature if temperature is not None else settings.ai_temperature,
            max_output_tokens=max_tokens if max_tokens is not None else DEFAULT_CLASSIFY_MAX_TOKENS,
        )
        response = self._client.models.generate_content(
            model=model or self._model,
            contents=user,
            config=config,
        )
        if response.text:
            return str(response.text)
        return ""

    async def analyze_chart(
        self,
        image_base64: str,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        model_override: str | None = None,  # noqa: ARG002 OpenRouter only
    ) -> str:
        """Analyze chart using native Gemini Vision (Google key — OR credit-drain fallback)."""
        if not self.is_configured():
            raise AIProviderUpstreamError(self.get_provider_name())

        try:
            response = await asyncio.to_thread(self._call_vision_api, image_base64, context, language)
            return self._format_response(response, language)
        except Exception as e:
            logger.exception("Gemini Vision error: %s", e)
            raise AIProviderUpstreamError(self.get_provider_name()) from e

    def _call_vision_api(self, image_base64: str, context: str, language: str = DEFAULT_LANGUAGE) -> str:
        """
        Make vision API call for chart analysis using NEW SDK.

        Uses centralized, reference-backed chart pattern metrics.
        """
        if not self._client:
            return "Gemini client not initialized."

        import base64

        from google.genai import types

        language_name = get_language_name(language)

        system_prompt = build_chart_analysis_reference_system_prompt()

        # Decode base64 to bytes for Gemini
        image_bytes = base64.b64decode(image_base64)

        prompt = f"""{system_prompt}

Analyze this cryptocurrency chart for reference-backed patterns:

{context}

IMPORTANT: Respond in {language_name}. Use natural, fluent {language_name}."""

        # NEW SDK: Create Part with inline_data for image
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")

        # NEW SDK: Use client.models.generate_content() with list of contents
        response = self._client.models.generate_content(
            model=self._model,
            contents=[prompt, image_part],
        )

        if response.text:
            return str(response.text)
        return "No analysis generated."
