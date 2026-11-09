"""
Subscription tier timeframe allowlists (SoT).

Values MUST exist in ``TIMEFRAME_REGISTRY``. Intersected with deployment
``supported_timeframes`` in ``subscription_entitlements.resolve_trading_timeframe_allowlist``.

@see apps/api/src/shared/constants/timeframes.py
"""

from __future__ import annotations

from src.shared.constants.timeframes import TIMEFRAME_REGISTRY

# Progressive intraday unlock: free → starter → pro → elite (all deployment-supported).
_TIMEFRAME_TIER_FREE_RAW: frozenset[str] = frozenset({"1h", "4h", "1d", "1w"})
_TIMEFRAME_TIER_STARTER_RAW: frozenset[str] = frozenset({"15m", "30m", "1h", "4h", "1d", "1w"})
# 2h/6h enter at PRO, alongside 5m/8h/12h/3d. Chosen deliberately as the most restrictive tier
# that still satisfies the "default-supported ⊆ pro" invariant: widening a tier later is trivial,
# whereas withdrawing a timeframe from users who already have it is a visible takeaway.
_TIMEFRAME_TIER_PRO_RAW: frozenset[str] = frozenset({"5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"})


def _assert_subset_of_registry(name: str, values: frozenset[str]) -> frozenset[str]:
    unknown = values - set(TIMEFRAME_REGISTRY.keys())
    if unknown:
        msg = f"{name} references unknown timeframes: {sorted(unknown)}"
        raise ValueError(msg)
    return values


TIMEFRAME_TIER_FREE: frozenset[str] = _assert_subset_of_registry("TIMEFRAME_TIER_FREE", _TIMEFRAME_TIER_FREE_RAW)
TIMEFRAME_TIER_STARTER: frozenset[str] = _assert_subset_of_registry("TIMEFRAME_TIER_STARTER", _TIMEFRAME_TIER_STARTER_RAW)
TIMEFRAME_TIER_PRO: frozenset[str] = _assert_subset_of_registry("TIMEFRAME_TIER_PRO", _TIMEFRAME_TIER_PRO_RAW)
