"""
OpenRouter AI Provider.

Free tier provider with vision support via multiple models.

WHY OpenRouter?
- FREE tier (50 requests/day, no credit card)
- Vision support with Qwen 2.5 VL
- Access to 300+ models
- OpenAI-compatible API

SDK Reference: https://openrouter.ai/docs
"""

import asyncio
import logging
from http import HTTPStatus
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


# Expected HTTP statuses: rate limit or upstream temporarily unavailable
_EXPECTED_STATUS_CODES = (429, 502, 503)

# Credit drain / privacy routing — raise so analyze_chart runtime chain can use native Gemini.
_CREDIT_OR_ROUTING_STATUS_CODES = (402, 404)


def is_openrouter_credit_or_routing_failure(status_code: int | None, message: str) -> bool:
    """True when OpenRouter cannot serve (credits empty / privacy blocks all endpoints).

    Gemini *on OpenRouter* still burns OpenRouter credits — drained balance requires a
    *native* Gemini (or Together) provider fallback, not another OR model slug.
    """
    if status_code == HTTPStatus.PAYMENT_REQUIRED:
        return True
    if status_code == HTTPStatus.NOT_FOUND:
        lowered = message.lower()
        return "data policy" in lowered or "guardrail" in lowered or "no endpoints" in lowered
    return False


def _is_expected_api_error(exc: BaseException) -> bool:
    """
    True if the exception is an expected API condition (rate limit, temporary outage).

    WHY: Log these as WARNING without traceback; they are handled and user gets a
    friendly message. Real bugs stay ERROR + traceback.
    """
    try:
        from openai import APIStatusError, RateLimitError

        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIStatusError):
            status = getattr(exc, "status_code", None)
            return status in _EXPECTED_STATUS_CODES
    except ImportError:
        pass
    return False


class OpenRouterAIProvider(KeyedAIProviderMixin, VisionAIProvider):
    """
    OpenRouter AI provider (FREE tier with vision support).

    WHY OpenRouter?
    - FREE tier (50 requests/day, no credit card required)
    - Vision support with Qwen 2.5 VL 7B
    - Access to 300+ models through unified API
    - OpenAI-compatible (easy integration)

    Cost: FREE tier with 50 requests/day
    Get key from: https://openrouter.ai/keys

    API: OpenAI-compatible chat completions
    Reference: https://openrouter.ai/docs/features/multimodal/images
    """

    _API_KEY_SETTING = "openrouter_api_key"
    _MODEL_SETTING = "ai_model_openrouter"
    _KEY_LABEL = "OpenRouter"
    _NOT_CONFIGURED_WARNING = "OpenRouter API key not configured. Get free key at openrouter.ai/keys"

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key. If None, uses settings.openrouter_api_key

        Raises:
            ValueError: If API key is empty string
        """
        # BEFORE delegating: `_configure_key_and_model` calls `_init_client`, and this provider's
        # client construction is free to read the vision model. Setting it after would leave the
        # attribute missing during that call.
        self._vision_model = settings.ai_model_openrouter_vision
        self._configure_key_and_model(api_key)

    def _init_client(self) -> None:
        """Initialize OpenRouter client using OpenAI SDK."""
        try:
            from openai import OpenAI

            from src.shared.constants.ai_provider_http import (
                AI_PROVIDER_REQUEST_TIMEOUT_SECONDS,
            )

            # Same explicit deadline as the Groq sibling, and for the same measured reason: an
            # unbounded LLM call does not fail, it hangs (4h47m on 6.3s of CPU, 2026-09-10). Set
            # here too rather than only where the incident happened — the next stall will not
            # politely pick the provider that was already fixed.
            # OpenRouter uses OpenAI-compatible API
            self._client = OpenAI(
                api_key=self._api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=AI_PROVIDER_REQUEST_TIMEOUT_SECONDS,
            )
            logger.info(
                "OpenRouterAIProvider initialized with model: %s, vision: %s",
                self._model,
                self._vision_model,
            )
        except ImportError:
            logger.warning("openai package not installed. Run: pip install openai")
            self._client = None
        except Exception as e:
            logger.exception("Failed to initialize OpenRouter client: %s", e)
            self._client = None

    def is_configured(self) -> bool:
        """Check if OpenRouter is configured."""
        return bool(self._api_key and self._client)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "openrouter"

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Generate explanation using OpenRouter in the specified language."""
        if not self.is_configured():
            return self._format_response(
                "AI explanation unavailable. OpenRouter API key not configured. Get a free key at openrouter.ai/keys",
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
            if _is_expected_api_error(e):
                logger.warning(
                    "OpenRouter API rate limit or temporary error: %s",
                    e,
                    exc_info=False,
                )
            else:
                logger.exception("OpenRouter API error: %s", e)
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
        """Make synchronous API call to OpenRouter."""
        if not self._client:
            return "OpenRouter client not initialized."

        language_name = get_language_name(language)

        prompt = f"""{SYSTEM_PROMPT}

Based on the following data, explain why this trading signal was generated:

{context}

IMPORTANT: Respond in {language_name}. Use natural, fluent {language_name}."""

        # OpenRouter uses OpenAI-compatible chat completions API.
        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "messages": [{"role": "user", "content": prompt}],
            "extra_headers": {
                "HTTP-Referer": "https://pulsai.live",
                "X-Title": "PulsAI Trading Platform",
            },
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
        """Lean classification via OpenRouter (OpenAI-compatible system + user roles)."""
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
            extra_headers={
                "HTTP-Referer": "https://pulsai.live",
                "X-Title": "PulsAI Trading Platform",
            },
        )
        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return ""

    async def analyze_chart(
        self,
        image_base64: str,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        model_override: str | None = None,
    ) -> str:
        """Analyze chart using OpenRouter Vision in the specified language.

        Credit drain (402) / privacy routing (404) raises ``AIProviderUpstreamError`` so
        ``analyze_chart_with_runtime_fallback`` can switch to *native* Gemini (Google key).
        A different OpenRouter vision slug is only a within-OR retry — it cannot help when
        OpenRouter credits are $0.
        """
        if not self.is_configured():
            raise AIProviderUpstreamError(self.get_provider_name())

        models: list[str] = []
        primary = model_override or self._vision_model
        models.append(primary)
        fallback_slug = (settings.ai_model_openrouter_vision_fallback or "").strip()
        if fallback_slug and fallback_slug not in models and model_override is None:
            models.append(fallback_slug)

        last_exc: BaseException | None = None
        for model in models:
            try:
                response = await asyncio.to_thread(self._call_vision_api, image_base64, context, language, model)
                return self._format_response(response, language)
            except Exception as e:
                last_exc = e
                status = getattr(e, "status_code", None)
                msg = str(e)
                if is_openrouter_credit_or_routing_failure(status, msg):
                    logger.warning(
                        "OpenRouter vision credit/routing failure model=%s: %s — raising for native fallback",
                        model,
                        e,
                    )
                    raise AIProviderUpstreamError(self.get_provider_name()) from e
                if _is_expected_api_error(e):
                    logger.warning(
                        "OpenRouter Vision temporary error model=%s: %s",
                        model,
                        e,
                        exc_info=False,
                    )
                    continue
                logger.exception("OpenRouter Vision error model=%s: %s", model, e)
                raise AIProviderUpstreamError(self.get_provider_name()) from e

        if last_exc is not None and _is_expected_api_error(last_exc):
            raise AIProviderUpstreamError(self.get_provider_name()) from last_exc
        raise AIProviderUpstreamError(self.get_provider_name())

    def _call_vision_api(
        self,
        image_base64: str,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        model: str | None = None,
    ) -> str:
        """
        Make vision API call for chart analysis.

        Uses centralized, reference-backed chart pattern metrics.
        """
        if not self._client:
            return "OpenRouter client not initialized."
        vision_model = model or self._vision_model

        language_name = get_language_name(language)

        system_prompt = build_chart_analysis_reference_system_prompt()

        prompt = f"""{system_prompt}

Analyze this cryptocurrency chart for reference-backed patterns:

{context}

IMPORTANT: Respond in {language_name}. Use natural, fluent {language_name}."""

        # OpenRouter vision uses OpenAI-compatible format with base64 images
        # Reference: https://openrouter.ai/docs/features/multimodal/images
        response = self._client.chat.completions.create(
            model=vision_model,
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
            extra_headers={
                "HTTP-Referer": "https://pulsai.live",
                "X-Title": "PulsAI Trading Platform",
            },
        )

        if response.choices and response.choices[0].message.content:
            return str(response.choices[0].message.content)
        return "No analysis generated."
