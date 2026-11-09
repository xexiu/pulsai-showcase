"""
SoT for admin billing magic values (refund metadata cap, Stripe tier/currency rules).

WHY a dedicated module:
- Routes and services import one place; tests assert the same constants.
"""

from __future__ import annotations

from typing import Final

from src.domain.enums import SubscriptionTier

# Stored in User.settings JSON (see admin billing currency helpers).
USER_BILLING_CURRENCY_SETTINGS_KEY: Final = "billing_currency"

DEFAULT_BILLING_CURRENCY_FALLBACK: Final = "eur"

SUPPORTED_BILLING_CURRENCIES: Final[frozenset[str]] = frozenset({"eur", "usd"})

# Stripe metadata max length; trim admin free-text before Refund.create.
ADMIN_REFUND_METADATA_MAX_CHARS: Final = 500

PAID_SYNC_TARGET_TIERS: Final[frozenset[str]] = frozenset(
    {
        SubscriptionTier.STARTER.value,
        SubscriptionTier.PRO.value,
        SubscriptionTier.ELITE.value,
    },
)
