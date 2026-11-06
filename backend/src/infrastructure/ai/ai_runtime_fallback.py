"""Try the next provider when the configured one ERRORS — as opposed to being unconfigured.

REUSE-AUDIT: considered src/infrastructure/ai/ai_provider_registry.py — the sibling extracted
from the same file in the same slice; not extending because its `_FALLBACK_CHAINS` answers a
DIFFERENT question ("this key is missing, who else is configured?") resolved once at selection
time, while the chains below are walked at CALL time after an upstream failure; its factories are
IMPORTED below. Considered src/infrastructure/ai/providers.py; not extending because it is the
651-line over-cap module this split fixes, and it re-exports these three coroutines unchanged.
Considered src/infrastructure/ai/ai_provider_base.py; not extending because
`AIProviderUpstreamError` is the exception this module catches, not a place to put retry policy —
it is IMPORTED below. Nothing is forked: each chain and coroutine exists exactly once, here.

MOVED here VERBATIM from `providers.py`.

WHY IT IS A UNIT. Four ordered chains and the three coroutines that walk them. The orders are not
interchangeable and each carries its measured reason — Groq is absent from every vision chain
because it has no `analyze_chart`; OpenRouter leads the news chain because its slot is routed to
the model validated at ~89% macro accuracy against FinBERT's ~44%; `mock` is the floor on every
chain so a total outage degrades instead of raising.

PATTERN (ARCHITECTURE_PATTERNS.md section 5): Retry, bounded — each chain is a fixed, finite list,
never an unbounded loop, which is that row's stated anti-fit. Section 5's honesty clause binds
too, and is satisfied: every fallback hop logs the provider it abandoned and the error that caused
it, and the caller receives the name of the provider that actually answered.

LAYER (DDD_PATTERNS.md): infrastructure. Vendor orchestration, no business rule of its own.

@see ai_provider_registry.py for construction, providers.py for the public facade
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from src.infrastructure.ai.ai_provider_base import (
    DEFAULT_LANGUAGE,
    AIProviderUpstreamError,
    VisionAIProvider,
)
from src.infrastructure.ai.ai_provider_registry import (
    _PROVIDER_FACTORIES,
    _get_or_create_mock,
    get_mock_mode,
)
from src.infrastructure.config.settings import settings

if TYPE_CHECKING:
    from src.infrastructure.persistence.user_model import User

logger = logging.getLogger(__name__)


# When the primary provider is configured but the upstream API fails (quota, outage, etc.),
# try the next in order. Differs from _FALLBACK_CHAINS (pick first *configured* key only).
_EXPLAIN_RUNTIME_CHAIN_PRO: tuple[str, ...] = (
    "claude",
    "openrouter",
    "together",
    "gemini",
    "groq",
    "mock",
)
_EXPLAIN_RUNTIME_CHAIN_FREE: tuple[str, ...] = (
    "groq",
    "openrouter",
    "together",
    "gemini",
    "mock",
)

# News-impact classification chain. Tier-independent: the news snapshot is a global
# worker task with no user, so there is no PRO/Claude path. OpenRouter is FIRST because
# its slot is routed to settings.ai_model_news_impact (DeepSeek-V3 — validated 2026-06 at
# ~89% macro accuracy vs FinBERT's ~44%; see src/research/news_impact_deepseek_eval.py).
# Groq/Together/Gemini are unvalidated free fallbacks (their own default models); mock is the
# always-present floor returning a NEUTRAL verdict so the blend degrades to FinBERT.
_CLASSIFY_NEWS_CHAIN: tuple[str, ...] = (
    "openrouter",
    "groq",
    "together",
    "gemini",
    "mock",
)

# Chart Analyze (vision). OpenRouter first; on credit drain / privacy 404 → native Gemini
# (Google key — separate billing). Together next; mock floor. Groq omitted (no vision).
_ANALYZE_CHART_RUNTIME_CHAIN: tuple[str, ...] = (
    "openrouter",
    "gemini",
    "together",
    "claude",
    "mock",
)


def _explain_runtime_provider_names(user: User | None) -> tuple[str, ...]:
    """Ordered provider ids for explain_signal runtime failover."""
    if get_mock_mode():
        return ("mock",)
    from src.domain.enums import SubscriptionTier

    tier = SubscriptionTier.FREE
    if user is not None:
        try:
            tier = SubscriptionTier(user.subscription_tier)
        except ValueError:
            tier = SubscriptionTier.FREE
    if tier in (SubscriptionTier.PRO, SubscriptionTier.ELITE):
        return _EXPLAIN_RUNTIME_CHAIN_PRO
    return _EXPLAIN_RUNTIME_CHAIN_FREE


def _analyze_chart_runtime_provider_names(user: User | None) -> tuple[str, ...]:
    """Ordered vision providers: OR → native Gemini (credit-drain fallback) → …"""
    del user  # Chart Analyze is Pro-gated at the route; chain is tier-independent.
    if get_mock_mode():
        return ("mock",)
    return _ANALYZE_CHART_RUNTIME_CHAIN


async def analyze_chart_with_runtime_fallback(
    user: User | None,
    *,
    image_base64: str,
    context: str,
    language: str = DEFAULT_LANGUAGE,
    model_override: str | None = None,
) -> tuple[str, str]:
    """Analyze a chart image, failing over when OpenRouter credits are drained.

    Gemini *via OpenRouter* still spends OpenRouter balance. When OR returns 402/privacy
    404, this walks to the **native** Gemini provider (``gemini_api_key``).

    Returns:
        (analysis_text, provider_name_used)
    """
    # Chain is vision-only (no Groq). Mirror explain_signal: try configured clients;
    # do not isinstance-gate (breaks test doubles; production classes already subclass).
    chain = _analyze_chart_runtime_provider_names(user)
    for name in chain:
        factory = _PROVIDER_FACTORIES[name]
        client = factory()
        if not client.is_configured():
            continue
        try:
            # `analyze_chart` lives on VisionAIProvider, not on AIProvider -- deliberate interface
            # segregation, since Groq and friends are text-only (see the note at the chain above).
            # The factories are typed to the base, so the call needs the narrower type.
            #
            # A cast rather than an isinstance gate, because the comment above this loop records
            # why gating breaks test doubles. A cast is only as good as its invariant, so the
            # invariant is TESTED: every name in `_ANALYZE_CHART_RUNTIME_CHAIN` must resolve to a
            # VisionAIProvider subclass (test_analyze_chart_chain_is_vision_only), which is what
            # makes this sound instead of hopeful.
            vision_client = cast("VisionAIProvider", client)
            text = await vision_client.analyze_chart(
                image_base64,
                context,
                language=language,
                model_override=model_override if name == "openrouter" else None,
            )
            return text, client.get_provider_name()
        except AIProviderUpstreamError as exc:
            logger.warning(
                "analyze_chart upstream failure for provider=%s, trying next: %s",
                name,
                exc.__cause__ or exc,
            )
    mock_client = _get_or_create_mock()
    text = await mock_client.analyze_chart(image_base64, context, language=language)
    return text, mock_client.get_provider_name()


async def explain_signal_with_runtime_fallback(
    user: User | None,
    context: str,
    language: str = DEFAULT_LANGUAGE,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
) -> tuple[str, str]:
    """
    Generate a signal explanation, trying providers in tier order until one succeeds.

    Per-call `temperature` / `max_tokens` / `model` overrides (typically supplied
    from the AIExplainConfigService admin snapshot) propagate to whichever provider
    serves the request. Pass ``None`` to use the provider's environment defaults.

    Returns:
        (explanation_text_with_disclaimer, provider_name_used)
    """
    chain = _explain_runtime_provider_names(user)
    for name in chain:
        factory = _PROVIDER_FACTORIES[name]
        client = factory()
        if not client.is_configured():
            continue
        try:
            text = await client.explain_signal(
                context,
                language=language,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
            return text, client.get_provider_name()
        except AIProviderUpstreamError as exc:
            logger.warning(
                "explain_signal upstream failure for provider=%s, trying next: %s",
                name,
                exc.__cause__ or exc,
            )
    mock_client = _get_or_create_mock()
    text = await mock_client.explain_signal(
        context,
        language=language,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    return text, mock_client.get_provider_name()


async def classify_text_with_news_fallback(
    *,
    system: str,
    user: str,
    max_tokens: int | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> str | None:
    """Lean classification across the free-first news chain; ``None`` if all fail.

    System task (no user / subscription tier). Walks the configured providers in
    ``_CLASSIFY_NEWS_CHAIN``, skips unconfigured ones, and on an upstream failure
    (including "provider does not support classification") tries the next. Returns
    the FIRST successful raw response. ``None`` only if every provider — including
    mock — failed, which the caller treats as "no verdict for this headline".

    AI mock mode (this flag) and FinBERT stub mode (the orchestrator's gate) are
    orthogonal: when AI mock mode is on, mock's NEUTRAL verdict is the correct safe
    degradation and the blend reduces to FinBERT regardless of FinBERT's own mode.
    """
    chain: tuple[str, ...] = ("mock",) if get_mock_mode() else _CLASSIFY_NEWS_CHAIN
    for name in chain:
        client = _PROVIDER_FACTORIES[name]()
        if not client.is_configured():
            continue
        # Route the OpenRouter slot to the validated news-impact model (DeepSeek-V3); other
        # providers keep their own default (a deepseek/* slug is meaningless to groq/together/
        # gemini). An explicit model= arg overrides this per-provider resolution.
        resolved_model = model or (settings.ai_model_news_impact if name == "openrouter" else None)
        try:
            return await client.classify_text(
                system=system,
                user=user,
                max_tokens=max_tokens,
                model=resolved_model,
                temperature=temperature,
            )
        except AIProviderUpstreamError as exc:
            logger.warning(
                "classify_text upstream failure for provider=%s, trying next: %s",
                name,
                exc.__cause__ or exc,
            )
    return None
