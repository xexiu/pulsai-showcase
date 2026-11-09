"""Behavior tests for Stripe price id ↔ tier mapping (checkout + webhooks SoT)."""

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from src.application.billing.admin_billing_constants import PAID_SYNC_TARGET_TIERS
from src.application.billing.stripe_prices import (
    paid_tier_values,
    stripe_price_id_for_tier,
    subscription_tier_for_stripe_price_id,
)
from src.domain.enums import SubscriptionTier

if TYPE_CHECKING:
    from src.infrastructure.config.settings import Settings


def _settings(**overrides: str) -> Settings:
    """Minimal Settings-like object for mapping tests."""
    base: dict[str, str] = {
        "stripe_price_starter": "price_starter_eur",
        "stripe_price_pro": "price_pro_eur",
        "stripe_price_elite": "price_elite_eur",
        "stripe_price_starter_usd": "price_starter_usd",
        "stripe_price_pro_usd": "price_pro_usd",
        "stripe_price_elite_usd": "price_elite_usd",
    }
    base.update(overrides)
    return SimpleNamespace(**base)  # type: ignore[return-value]


def test_paid_tier_values_matches_admin_sync_constants() -> None:
    """Paid checkout tiers must stay aligned with admin sync-tier allowlist (ADR-016)."""
    assert paid_tier_values() == PAID_SYNC_TARGET_TIERS


def test_paid_tier_values_contains_only_starter_pro_elite() -> None:
    assert paid_tier_values() == frozenset(
        {
            SubscriptionTier.STARTER.value,
            SubscriptionTier.PRO.value,
            SubscriptionTier.ELITE.value,
        }
    )


@pytest.mark.parametrize(
    ("currency", "expected"),
    [
        ("eur", "price_starter_eur"),
        ("usd", "price_starter_usd"),
    ],
)
def test_stripe_price_id_for_tier_respects_currency(currency: str, expected: str) -> None:
    settings = _settings()
    got = stripe_price_id_for_tier(settings, SubscriptionTier.STARTER.value, currency=currency)
    assert got == expected


def test_stripe_price_id_for_tier_defaults_currency_to_eur() -> None:
    settings = _settings()
    assert stripe_price_id_for_tier(settings, SubscriptionTier.PRO.value) == settings.stripe_price_pro


def test_stripe_price_id_for_tier_returns_none_when_unconfigured() -> None:
    settings = _settings(stripe_price_starter="")
    assert stripe_price_id_for_tier(settings, SubscriptionTier.STARTER.value) is None


def test_stripe_price_id_for_tier_strips_whitespace() -> None:
    settings = _settings(stripe_price_starter="  price_x  ")
    assert stripe_price_id_for_tier(settings, SubscriptionTier.STARTER.value) == "price_x"


@pytest.mark.parametrize(
    ("price_field", "tier_value"),
    [
        ("stripe_price_starter", SubscriptionTier.STARTER.value),
        ("stripe_price_pro", SubscriptionTier.PRO.value),
        ("stripe_price_elite", SubscriptionTier.ELITE.value),
        ("stripe_price_starter_usd", SubscriptionTier.STARTER.value),
        ("stripe_price_pro_usd", SubscriptionTier.PRO.value),
        ("stripe_price_elite_usd", SubscriptionTier.ELITE.value),
    ],
)
def test_subscription_tier_for_stripe_price_id_round_trip(price_field: str, tier_value: str) -> None:
    settings = _settings()
    price_id = getattr(settings, price_field)
    assert subscription_tier_for_stripe_price_id(settings, price_id) == tier_value


def test_subscription_tier_for_stripe_price_id_unknown_returns_none() -> None:
    settings = _settings()
    assert subscription_tier_for_stripe_price_id(settings, "price_unknown") is None


def test_subscription_tier_for_stripe_price_id_empty_returns_none() -> None:
    settings = _settings()
    assert subscription_tier_for_stripe_price_id(settings, "") is None
