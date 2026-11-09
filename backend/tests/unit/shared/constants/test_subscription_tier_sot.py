"""SubscriptionTier SoT regression.

Guards against scattered ``"free"`` / ``"starter"`` string literals. All
tier-gating code MUST compare against ``SubscriptionTier.FREE.value`` etc.
"""

from __future__ import annotations

from src.domain.enums import SubscriptionTier


def test_subscription_tier_values_are_stable_lowercase_db_keys() -> None:
    """DB ``users.subscription_tier`` SqlEnum pin — must not drift from these four strings."""
    assert SubscriptionTier.FREE.value == "free"
    assert SubscriptionTier.STARTER.value == "starter"
    assert SubscriptionTier.PRO.value == "pro"
    assert SubscriptionTier.ELITE.value == "elite"


def test_subscription_tier_is_str_enum() -> None:
    """StrEnum so equality against a plain ``str`` column value works without ``.value``."""
    assert SubscriptionTier.FREE == "free"


# =============================================================================
# Coercion at the str|enum boundary — pins the SoT helper that fixes the
# ``'str' object has no attribute 'can_access'`` runtime AttributeError that
# crashed ``/api/v1/ai/explain`` when SQLAlchemy returned ``user.subscription_tier``
# as a raw ``str`` (Mapped[str] column) and the RAG section registry's
# ``iter_effective`` called ``.can_access()`` on it.
# =============================================================================


class TestSubscriptionTierCoerce:
    def test_coerce_returns_enum_unchanged(self) -> None:
        """Already-enum input pass-through (no double-conversion overhead)."""
        assert SubscriptionTier.coerce(SubscriptionTier.PRO) is SubscriptionTier.PRO

    def test_coerce_string_returns_enum(self) -> None:
        """The actual production bug: SQLAlchemy ``Mapped[str]`` value → enum.

        Without this, every chained ``.can_access`` / ``._tier_level`` call
        downstream of an ORM-hydrated user crashes with AttributeError.
        """
        assert SubscriptionTier.coerce("free") is SubscriptionTier.FREE
        assert SubscriptionTier.coerce("starter") is SubscriptionTier.STARTER
        assert SubscriptionTier.coerce("pro") is SubscriptionTier.PRO
        assert SubscriptionTier.coerce("elite") is SubscriptionTier.ELITE

    def test_coerce_none_returns_none(self) -> None:
        """``None`` is a sentinel for "unauthenticated / no tier" — preserve it."""
        assert SubscriptionTier.coerce(None) is None

    def test_coerce_unknown_string_returns_none(self) -> None:
        """An unknown string maps to None (DEFENSIVE — never crash a request).

        A misspelled tier or a future-tier rollback should NOT 500 the request.
        Downstream tier-gating treats ``None`` as "lowest tier, no access".
        """
        assert SubscriptionTier.coerce("admin") is None
        assert SubscriptionTier.coerce("") is None
        assert SubscriptionTier.coerce("FREE") is None  # case-sensitive

    def test_coerce_non_string_returns_none(self) -> None:
        """Defensive against unexpected types (numbers, lists, etc.)."""
        assert SubscriptionTier.coerce(42) is None  # type: ignore[arg-type]
        assert SubscriptionTier.coerce([]) is None  # type: ignore[arg-type]

    def test_coerced_value_supports_can_access(self) -> None:
        """End-to-end: coerce a string, then call ``.can_access`` — the
        exact code path that crashed the AI-explain endpoint pre-fix."""
        tier = SubscriptionTier.coerce("pro")
        assert tier is not None
        assert tier.can_access(SubscriptionTier.FREE) is True
        assert tier.can_access(SubscriptionTier.ELITE) is False
