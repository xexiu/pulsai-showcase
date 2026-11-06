"""
Groq AI Provider.

Free tier provider using Llama 3 for fast inference.

Extracted from providers.py for modularity.
"""

import asyncio
import logging

from src.infrastructure.ai.ai_provider_base import (
    DEFAULT_CLASSIFY_MAX_TOKENS,
    DEFAULT_LANGUAGE,
    SYSTEM_PROMPT,
    AIProvider,
    AIProviderUpstreamError,
    get_language_name,
)
from src.infrastructure.ai.ai_provider_keyed import KeyedAIProviderMixin
from src.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)


class GroqAIProvider(KeyedAIProviderMixin, AIProvider):
    """
    Groq AI provider using Llama 3 (free tier).

    WHY Groq?
    - FREE tier with generous limits
    - Very fast inference (LPU architecture)
    - Good quality with Llama 3 70B
    - No credit card required

    Rate limits (free tier):
    - ~30 requests/minute
    - ~6000 tokens/minute
    """

    _API_KEY_SETTING = "groq_api_key"
    _MODEL_SETTING = "ai_model_groq"
    _KEY_LABEL = "Groq"
    _NOT_CONFIGURED_WARNING = "Groq API key not configured. Get free key at console.groq.com"

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize Groq client.

        Args:
            api_key: Groq API key. If None, uses settings.groq_api_key

        Raises:
            ValueError: If API key is empty string
        """
        self._configure_key_and_model(api_key)

    def _init_client(self) -> None:
        """Initialize Groq client."""
        try:
            from groq import Groq

            from src.shared.constants.ai_provider_http import (
                AI_PROVIDER_REQUEST_TIMEOUT_SECONDS,
            )

            # An EXPLICIT deadline, not the SDK's default. Measured 2026-09-10: a research run
            # holding one ESTABLISHED socket to Groq sat 4h47m on 6.3s of CPU and neither
            # finished nor failed. The same client serves /explain-signal, where an unbounded
            # call holds a worker instead of a night.
            self._client = Groq(
                api_key=self._api_key,
                timeout=AI_PROVIDER_REQUEST_TIMEOUT_SECONDS,
            )
            logger.info("GroqAIProvider initialized with model: %s", self._model)
        except ImportError:
            logger.warning("groq package not installed. Run: pip install groq")
            self._client = None
        except Exception as e:
            logger.exception("Failed to initialize Groq client: %s", e)
            self._client = None

    def is_configured(self) -> bool:
        """Check if Groq is configured."""
        return bool(self._api_key and self._client)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "groq"

    async def explain_signal(
        self,
        context: str,
        language: str = DEFAULT_LANGUAGE,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        """Generate explanation using Groq/Llama in the specified language."""
        if not self.is_configured():
            return self._format_response(
                "AI explanation unavailable. Groq API key not configured. Get a free key at console.groq.com",
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
            logger.exception("Groq API error: %s", e)
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
        """Make synchronous API call to Groq."""
        if not self._client:
            return "Groq client not initialized."

        language_name = get_language_name(language)

        chat_completion = self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Based on the following data, explain why this "
                        f"trading signal was generated:\n\n{context}\n\n"
                        f"IMPORTANT: Respond in {language_name}. "
                        f"Use natural, fluent {language_name}."
                    ),
                },
            ],
            model=model or self._model,
            temperature=temperature if temperature is not None else settings.ai_temperature,
            max_tokens=max_tokens or 2000,
        )

        if chat_completion.choices:
            return chat_completion.choices[0].message.content or "No explanation generated."
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
        """Lean classification via Groq (OpenAI-compatible system + user roles)."""
        if not self._client:
            raise AIProviderUpstreamError(self.get_provider_name())
        chat_completion = self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model or self._model,
            temperature=temperature if temperature is not None else settings.ai_temperature,
            max_tokens=max_tokens if max_tokens is not None else DEFAULT_CLASSIFY_MAX_TOKENS,
        )
        if chat_completion.choices:
            return chat_completion.choices[0].message.content or ""
        return ""
