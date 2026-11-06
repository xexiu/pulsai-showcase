"""
AI Provider Abstraction (Sprint 1.7)

Multi-provider AI system supporting:
- Mock mode (free, for testing)
- Groq (free tier, Llama 3, text only)
- Claude (paid, premium, vision)
- Gemini (free tier, vision - requires billing in some regions)
- Together.ai (free tier, vision - requires initial deposit)
- OpenRouter (FREE tier, vision - NO credit card required) - RECOMMENDED

USAGE:
```python
from src.infrastructure.ai.providers import get_ai_client

client = get_ai_client()
explanation = await client.explain_signal(context)
```

WHY multi-provider?
- Mock: Zero cost development/testing
- Groq: Free tier for production (rate limited, no vision)
- Claude: Premium option for users willing to pay
- Gemini: Free tier with vision support (may require billing setup)
- Together.ai: Free tier with vision (requires initial deposit)
- OpenRouter: FREE tier with vision, no credit card needed (RECOMMENDED)

REFACTORED: Providers split into sub-modules for maintainability:
- ai_provider_base.py: AIProvider ABC and constants
- ai_provider_mock.py: MockAIProvider
- ai_provider_groq.py: GroqAIProvider
- ai_provider_claude.py: ClaudeAIProvider
- ai_provider_gemini.py: GeminiAIProvider
- ai_provider_together.py: TogetherAIProvider
- ai_provider_openrouter.py: OpenRouterAIProvider

This file contains factory functions and re-exports for backward compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

# Re-export base class and constants
from src.infrastructure.ai.ai_provider_base import (
    DEFAULT_LANGUAGE,
    DISCLAIMER,
    DISCLAIMERS,
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    SYSTEM_PROMPT,
    AIProvider,
    AIProviderUpstreamError,
    VisionAIProvider,
    get_language_name,
)
from src.infrastructure.ai.ai_provider_claude import ClaudeAIProvider
from src.infrastructure.ai.ai_provider_gemini import GeminiAIProvider
from src.infrastructure.ai.ai_provider_groq import GroqAIProvider

# Re-export provider implementations
from src.infrastructure.ai.ai_provider_mock import MockAIProvider
from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider
from src.infrastructure.ai.ai_provider_openrouter import OpenRouterAIProvider
from src.infrastructure.ai.ai_provider_registry import (
    _FALLBACK_CHAINS,
    _get_or_create_claude,
    _get_or_create_gemini,
    _get_or_create_groq,
    _get_or_create_mock,
    _get_or_create_openrouter,
    _get_or_create_together,
    _try_provider_with_fallback,
    get_mock_mode,
    set_mock_mode,
)
from src.infrastructure.ai.ai_provider_together import TogetherAIProvider
from src.infrastructure.ai.ai_runtime_fallback import (
    analyze_chart_with_runtime_fallback,
    classify_text_with_news_fallback,
    explain_signal_with_runtime_fallback,
)
from src.infrastructure.config.settings import settings

if TYPE_CHECKING:
    from src.infrastructure.persistence.user_model import User

logger = logging.getLogger(__name__)

# Explicit __all__ for type checkers and IDE support
__all__ = [
    "DEFAULT_LANGUAGE",
    "DISCLAIMER",
    "DISCLAIMERS",
    "LANGUAGE_NAMES",
    "SUPPORTED_LANGUAGES",
    "SYSTEM_PROMPT",
    "AIProvider",
    "AIProviderUpstreamError",
    "ClaudeAIProvider",
    "GeminiAIProvider",
    "GroqAIProvider",
    "MockAIProvider",
    "OllamaAIProvider",
    "OpenRouterAIProvider",
    "TogetherAIProvider",
    "VisionAIProvider",
    "analyze_chart_with_runtime_fallback",
    "classify_text_with_news_fallback",
    "explain_signal_with_runtime_fallback",
    "get_ai_client",
    "get_ai_client_for_user",
    "get_available_providers",
    "get_language_name",
    "get_mock_mode",
    "set_mock_mode",
]


# =============================================================================
# Provider Factory
# =============================================================================


def get_ai_client_for_user(user: User | None) -> AIProvider:
    """
    Select AI provider from subscription tier (ADR-010).

    BUSINESS RULES:
    - Global mock mode still wins (admin demos, tests).
    - Pro / Elite → Claude primary (premium quality).
    - Free / Starter / anonymous → Groq primary (free tier; anonymous treated as free).

    FALLBACK CHAINS:
    Reuse the same per-provider chains as get_ai_client so misconfiguration degrades safely.

    NOTE: That only picks the first *configured* client. For explain-signal, upstream failures
    (quota, outage) are handled by explain_signal_with_runtime_fallback (runtime chain).
    """
    from src.domain.enums import SubscriptionTier

    if get_mock_mode():
        return _get_or_create_mock()

    tier = SubscriptionTier.FREE
    if user is not None:
        try:
            tier = SubscriptionTier(user.subscription_tier)
        except ValueError:
            tier = SubscriptionTier.FREE

    if tier in (SubscriptionTier.PRO, SubscriptionTier.ELITE):
        return _try_provider_with_fallback(
            "claude",
            _FALLBACK_CHAINS["claude"],
        )

    return _try_provider_with_fallback("groq", _FALLBACK_CHAINS["groq"])


def get_ai_client() -> AIProvider:
    """
    Get the appropriate AI client based on configuration.

    Priority:
    1. Mock mode override (if enabled via API or settings)
    2. Configured provider (openrouter, together, gemini, groq, claude, mock)

    Returns:
        Configured AIProvider instance
    """
    # Check mock mode first
    if get_mock_mode():
        return _get_or_create_mock()

    # Get provider based on settings
    provider = settings.ai_provider

    # Handle mock provider (no fallback needed)
    if provider == "mock":
        return _get_or_create_mock()

    # Handle providers with fallback chains
    fallback_chain = _FALLBACK_CHAINS.get(provider, _FALLBACK_CHAINS["claude"])
    return _try_provider_with_fallback(provider, fallback_chain)


def get_available_providers() -> list[dict[str, Any]]:
    """
    Get list of available AI providers with their status.

    Returns:
        List of provider info dicts for admin UI
    """
    # Through the registry's own factories, NOT a second copy of the double-checked lazy init.
    # This function used to re-implement it (its own `global` + `with _provider_init_lock`), so
    # two places knew how to construct the same five singletons while only one held the cache.
    # Splitting the registry out turned that quiet DRY violation into a NameError, which is the
    # useful half of the split.
    groq = _get_or_create_groq()
    claude = _get_or_create_claude()
    gemini = _get_or_create_gemini()
    together = _get_or_create_together()
    openrouter = _get_or_create_openrouter()
    # Ollama deliberately NOT constructed here: `get_ai_status` (api/v1/endpoints/ai_admin.py)
    # is `async def` and calls this function directly on the event loop, unlike every keyed
    # provider above (a cheap settings read + SDK object construction, no I/O). OllamaAIProvider
    # probes a live socket in `_init_client()` — building it here would run a blocking httpx call
    # straight on the event loop of a production admin endpoint on every request, the same class
    # of incident commit c2e25c565 fixed for the outbound LLM calls themselves. `_PROVIDER_
    # FACTORIES["ollama"]` below still resolves it lazily for anything that asks for it by name.

    return [
        {
            "id": "mock",
            "name": "Mock (Development)",
            "configured": True,
            "cost": "Free",
            "description": "Template responses for testing",
            "has_vision": False,
        },
        {
            "id": "groq",
            "name": "Groq (Llama 3)",
            "configured": groq.is_configured(),
            "cost": "Free tier",
            "description": "Fast, free inference with Llama 3 (NO vision)",
            "has_vision": False,
        },
        {
            "id": "openrouter",
            "name": "OpenRouter (Qwen VL)",
            "configured": openrouter.is_configured(),
            "cost": "Free tier",
            "description": "FREE with vision, no credit card (RECOMMENDED)",
            "has_vision": True,
        },
        {
            "id": "together",
            "name": "Together.ai (Llama 4)",
            "configured": together.is_configured(),
            "cost": "Free tier*",
            "description": "Free with vision (requires initial deposit)",
            "has_vision": True,
        },
        {
            "id": "gemini",
            "name": "Gemini (Google)",
            "configured": gemini.is_configured(),
            "cost": "Free tier*",
            "description": "Free with vision (may require billing setup)",
            "has_vision": True,
        },
        {
            "id": "claude",
            "name": "Claude (Anthropic)",
            "configured": claude.is_configured(),
            "cost": "Paid",
            "description": "Premium quality, best vision support",
            "has_vision": True,
        },
    ]
