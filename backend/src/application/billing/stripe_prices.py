"""
Map subscription tiers to Stripe Price IDs and reverse-resolve Price → tier.

WHY a dedicated module:
- Checkout and webhooks must agree on the same mapping (single SoT).
- Settings hold raw env strings; validation happens at call sites.
"""

from src.domain.enums import SubscriptionTier
from src.infrastructure.config.settings import Settings


def paid_tier_values() -> frozenset[str]:
    """Tiers that can be purchased via self-serve Checkout (excludes free)."""
    return frozenset(
        {
            SubscriptionTier.STARTER.value,
            SubscriptionTier.PRO.value,
            SubscriptionTier.ELITE.value,
        }
    )


def stripe_price_id_for_tier(
    settings: Settings,
    tier: str,
    *,
    currency: str = "eur",
) -> str | None:
    """
    Return configured Stripe Price id for a paid tier, or None if missing.

    Empty env string means “not configured” for that tier.

    Args:
        currency: ``eur`` (default) uses STRIPE_PRICE_*; ``usd`` uses STRIPE_PRICE_*_USD when set.
    """
    cur = (currency or "eur").strip().lower()
    if cur == "usd":
        mapping = {
            SubscriptionTier.STARTER.value: settings.stripe_price_starter_usd,
            SubscriptionTier.PRO.value: settings.stripe_price_pro_usd,
            SubscriptionTier.ELITE.value: settings.stripe_price_elite_usd,
        }
    else:
        mapping = {
            SubscriptionTier.STARTER.value: settings.stripe_price_starter,
            SubscriptionTier.PRO.value: settings.stripe_price_pro,
            SubscriptionTier.ELITE.value: settings.stripe_price_elite,
        }
    price_id = mapping.get(tier)
    if not price_id or not str(price_id).strip():
        return None
    return str(price_id).strip()


def subscription_tier_for_stripe_price_id(settings: Settings, price_id: str) -> str | None:
    """
    Resolve a recurring Price id back to our subscription_tier string.

    Used by subscription.updated webhooks when the active price changes.
    """
    if not price_id:
        return None
    normalized = price_id.strip()
    if settings.stripe_price_starter and normalized == settings.stripe_price_starter.strip():
        return SubscriptionTier.STARTER.value
    if settings.stripe_price_pro and normalized == settings.stripe_price_pro.strip():
        return SubscriptionTier.PRO.value
    if settings.stripe_price_elite and normalized == settings.stripe_price_elite.strip():
        return SubscriptionTier.ELITE.value
    starter_usd = settings.stripe_price_starter_usd
    if starter_usd and normalized == starter_usd.strip():
        return SubscriptionTier.STARTER.value
    if settings.stripe_price_pro_usd and normalized == settings.stripe_price_pro_usd.strip():
        return SubscriptionTier.PRO.value
    if settings.stripe_price_elite_usd and normalized == settings.stripe_price_elite_usd.strip():
        return SubscriptionTier.ELITE.value
    return None
