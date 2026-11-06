"""One place that builds an AI provider, caches it, and falls back when it is unconfigured.

REUSE-AUDIT: considered src/infrastructure/ai/providers.py; not extending because it is the
651-line over-cap module this split fixes, and it keeps its `__all__` facade by IMPORTING every
name below. Considered src/infrastructure/ai/ai_provider_base.py; not extending because it
declares the `AIProvider` / `VisionAIProvider` contracts and the shared prompts, and building or
caching instances there would put lifecycle in the interface — it is IMPORTED below. Considered
src/infrastructure/ai/ai_provider_mock.py and its six sibling implementations; not extending
because each knows only its own vendor, while the question here is which one to hand back — all
seven are IMPORTED below. Considered src/infrastructure/config/settings.py; not extending because
it reports which keys are configured and holds no construction — IMPORTED below. Nothing is
forked: each singleton and factory exists exactly once, here.

MOVED here VERBATIM from `providers.py`.

WHY IT IS A UNIT. The seven module-level singletons, the lock that protects their lazy
initialisation, the runtime mock-mode override and the CONFIGURED-provider fallback chain are one
piece of mutable state with one set of readers. Splitting them across files would be splitting a
cache from its guard.

ARCHITECTURE_PATTERNS.md section 1 calls a Singleton a liability when it is "really global mutable
state", and that is exactly what these are — so the mitigation is stated rather than assumed: the
instances are provider CLIENTS (stateless wrappers over an HTTP key), `_provider_init_lock` makes
construction atomic across concurrent requests, and `_mock_mode_override` is the one genuinely
mutable value, written only by `set_mock_mode`.

LAYER (DDD_PATTERNS.md): infrastructure. Vendor clients and their lifecycle.

@see providers.py for the public facade, ai_runtime_fallback.py for retry-on-upstream-error
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.infrastructure.ai.ai_provider_claude import ClaudeAIProvider
from src.infrastructure.ai.ai_provider_gemini import GeminiAIProvider
from src.infrastructure.ai.ai_provider_groq import GroqAIProvider
from src.infrastructure.ai.ai_provider_mock import MockAIProvider
from src.infrastructure.ai.ai_provider_ollama import OllamaAIProvider
from src.infrastructure.ai.ai_provider_openrouter import OpenRouterAIProvider
from src.infrastructure.ai.ai_provider_together import TogetherAIProvider
from src.infrastructure.config.settings import settings

if TYPE_CHECKING:
    from src.infrastructure.ai.ai_provider_base import AIProvider


logger = logging.getLogger(__name__)


# Singleton instances (lazy initialized)
_mock_provider: MockAIProvider | None = None
_groq_provider: GroqAIProvider | None = None
_claude_provider: ClaudeAIProvider | None = None
_gemini_provider: GeminiAIProvider | None = None
_together_provider: TogetherAIProvider | None = None
_openrouter_provider: OpenRouterAIProvider | None = None
_ollama_provider: OllamaAIProvider | None = None

# Protect lazy singleton initialization across concurrent callers.
_provider_init_lock = threading.Lock()

# Runtime mock mode override (can be changed via API)
_mock_mode_override: bool | None = None

# Fallback chains for each provider (ordered list of fallback providers)
_FALLBACK_CHAINS: dict[str, list[str]] = {
    "groq": ["mock"],
    "gemini": ["together", "mock"],
    "together": ["groq", "mock"],
    # Groq is text-only (no analyze_chart) — never put it on a vision chain.
    "openrouter": ["gemini", "together", "mock"],
    "claude": ["openrouter", "gemini", "together", "mock"],
}


def set_mock_mode(enabled: bool) -> None:
    """
    Enable/disable mock mode at runtime.

    WHY runtime toggle?
    - Admin can switch without server restart
    - Useful for testing in production
    - Saves costs during demos
    """
    global _mock_mode_override
    _mock_mode_override = enabled
    logger.info("AI Mock mode %s", "ENABLED" if enabled else "DISABLED")


def get_mock_mode() -> bool:
    """Get current mock mode status."""
    if _mock_mode_override is not None:
        return _mock_mode_override
    return settings.ai_mock_mode


def _get_or_create_mock() -> MockAIProvider:
    """Get or create mock provider singleton."""
    global _mock_provider
    if _mock_provider is None:
        with _provider_init_lock:
            if _mock_provider is None:
                _mock_provider = MockAIProvider()
    return _mock_provider


def _get_or_create_groq() -> GroqAIProvider:
    """Get or create Groq provider singleton."""
    global _groq_provider
    if _groq_provider is None:
        with _provider_init_lock:
            if _groq_provider is None:
                _groq_provider = GroqAIProvider()
    return _groq_provider


def _get_or_create_claude() -> ClaudeAIProvider:
    """Get or create Claude provider singleton."""
    global _claude_provider
    if _claude_provider is None:
        with _provider_init_lock:
            if _claude_provider is None:
                _claude_provider = ClaudeAIProvider()
    return _claude_provider


def _get_or_create_gemini() -> GeminiAIProvider:
    """Get or create Gemini provider singleton."""
    global _gemini_provider
    if _gemini_provider is None:
        with _provider_init_lock:
            if _gemini_provider is None:
                _gemini_provider = GeminiAIProvider()
    return _gemini_provider


def _get_or_create_together() -> TogetherAIProvider:
    """Get or create Together provider singleton."""
    global _together_provider
    if _together_provider is None:
        with _provider_init_lock:
            if _together_provider is None:
                _together_provider = TogetherAIProvider()
    return _together_provider


def _get_or_create_openrouter() -> OpenRouterAIProvider:
    """Get or create OpenRouter provider singleton."""
    global _openrouter_provider
    if _openrouter_provider is None:
        with _provider_init_lock:
            if _openrouter_provider is None:
                _openrouter_provider = OpenRouterAIProvider()
    return _openrouter_provider


def _get_or_create_ollama() -> OllamaAIProvider:
    """Get or create Ollama provider singleton.

    Local-only (no API key): deliberately NOT added to any runtime fallback chain
    (``_FALLBACK_CHAINS`` / ``_EXPLAIN_RUNTIME_CHAIN_*`` / ``_CLASSIFY_NEWS_CHAIN`` /
    ``_ANALYZE_CHART_RUNTIME_CHAIN``) — a developer's local server is never a candidate for
    production traffic failover. Registered here only so ``--provider ollama`` style explicit
    selection (e.g. research scripts) can resolve it the same way every other provider does.
    """
    global _ollama_provider
    if _ollama_provider is None:
        with _provider_init_lock:
            if _ollama_provider is None:
                _ollama_provider = OllamaAIProvider()
    return _ollama_provider


_PROVIDER_FACTORIES: dict[str, Callable[[], AIProvider]] = {
    "mock": _get_or_create_mock,
    "groq": _get_or_create_groq,
    "claude": _get_or_create_claude,
    "gemini": _get_or_create_gemini,
    "together": _get_or_create_together,
    "openrouter": _get_or_create_openrouter,
    "ollama": _get_or_create_ollama,
}


def _try_provider_with_fallback(
    provider_name: str,
    fallbacks: list[str],
) -> AIProvider:
    """
    Try to get a configured provider, falling back through chain if needed.

    WHY this pattern?
    - Centralizes fallback logic (DRY)
    - Makes fallback chains explicit and maintainable
    - Reduces complexity in main factory function

    Args:
        provider_name: Name of primary provider to try
        fallbacks: Ordered list of fallback provider names

    Returns:
        First configured provider found, or mock as final fallback
    """
    # Try primary provider
    primary_factory = _PROVIDER_FACTORIES[provider_name]
    primary_provider = primary_factory()

    if primary_provider.is_configured():
        return primary_provider

    # Try fallback chain
    logger.warning(
        "%s not configured, trying fallbacks",
        provider_name.capitalize(),
    )
    for fallback_name in fallbacks:
        fallback_factory = _PROVIDER_FACTORIES[fallback_name]
        fallback_provider = fallback_factory()

        if fallback_provider.is_configured():
            logger.info("Using fallback provider: %s", fallback_name)
            return fallback_provider

        logger.warning(
            "%s not configured, trying next fallback",
            fallback_name.capitalize(),
        )

    # Final fallback to mock
    logger.warning("All providers failed, falling back to mock")
    return _get_or_create_mock()
