"""OpenRouter vision: credit/privacy failures must raise so Gemini-native can fallback.

DISMISSAL-CHECK: not a hypothesis (shared infra tests).
"""

from __future__ import annotations

from src.infrastructure.ai.ai_provider_openrouter import is_openrouter_credit_or_routing_failure


def test_402_is_credit_failure() -> None:
    assert is_openrouter_credit_or_routing_failure(402, "Payment Required") is True


def test_404_privacy_is_routing_failure() -> None:
    assert (
        is_openrouter_credit_or_routing_failure(
            404,
            "No endpoints available matching your guardrail restrictions and data policy",
        )
        is True
    )


def test_429_is_not_credit_routing_for_raise_path() -> None:
    # Rate limit stays soft-handled inside the provider; not a credit-drain signal.
    assert is_openrouter_credit_or_routing_failure(429, "rate limit") is False
