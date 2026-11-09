"""Resolve futures leverage for DB persistence from CCXT ``create_order`` payloads.

Placement code already carries ``leverage_for_persist`` from pre-trade ``set_leverage``.
Some venue responses still omit denormalized leverage on later hydration paths; we treat the
raw CCXT order (especially ``info``) as the reconciliation source when present.

See also :mod:`paper_order_persistence` — ``PaperOrder.leverage`` /
``PaperTrade.leverage`` drive GET /trading/trades Historial APAL column.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from src.shared.constants.exchanges import MARKET_TYPE_SWAP, MarketType

__all__ = [
    "extract_leverage_int_from_ccxt_order",
    "leverage_for_db_from_ccxt_response",
]


def _parse_leverage_scalar(val: Any) -> int | None:
    if val is None:
        return None
    try:
        n = int(Decimal(str(val)))
    except InvalidOperation, ValueError, TypeError:
        return None
    return n if n >= 1 else None


def extract_leverage_int_from_ccxt_order(ccxt_order: dict[str, Any] | None) -> int | None:
    """Best-effort leverage from a unified CCXT order dict (top-level + ``info``).

    Exchange-specific keys vary; we scan a small allowlist used by USDT-M adapters.
    """
    if not ccxt_order:
        return None
    lev = _parse_leverage_scalar(ccxt_order.get("leverage"))
    if lev is not None:
        return lev
    info = ccxt_order.get("info")
    if not isinstance(info, dict):
        return None
    for key in (
        "leverage",
        "holdLeverage",
        "openLeverage",
        "openAvgLeverage",
        "marginLeverage",
        "lever",
    ):
        lev = _parse_leverage_scalar(info.get(key))
        if lev is not None:
            return lev
    return None


def leverage_for_db_from_ccxt_response(
    *,
    market_type: MarketType,
    ccxt_order: dict[str, Any] | None,
    placement_leverage: int | None,
) -> int | None:
    """Prefer venue-reported leverage from the CCXT order response, then placement leverage.

    Spot orders ignore CCXT leverage (typically absent); swap rows use exchange-first merge.
    """
    if market_type != MARKET_TYPE_SWAP:
        return placement_leverage
    venue = extract_leverage_int_from_ccxt_order(ccxt_order)
    if venue is not None:
        return venue
    return placement_leverage
