"""
Closed-trade **leg** breakdown for the Estadísticas tab — complements aggregate KPIs.

Counts **all** trade legs in the window (buy vs sell) and partitions **closed**
realized sells (non-null realized P&L on the sell leg) by the parent order's
``order_type`` (market vs limit). Rows whose parent is missing or not
market/limit land in ``other`` so we never silently drop activity.

Pure functions — no I/O. Callers supply normalized rows + an ``order_id →
order_type`` map built from the orders ledger in the same window.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from src.shared.constants.paper_trading import (
    ORDER_SIDE_BUY,
    ORDER_SIDE_SELL,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
)


@dataclass(frozen=True)
class LegBreakdownInputRow:
    """One fill row in the stats window (demo or paper)."""

    side: str
    order_id: str | None
    realized_pnl_usd: Decimal | None


@dataclass(frozen=True)
class ClosedTradeLegBreakdownResult:
    trade_legs_buy_count: int
    trade_legs_sell_count: int
    closed_realized_sell_market_count: int
    closed_realized_sell_limit_count: int
    closed_realized_sell_order_type_other_count: int


def compute_closed_trade_leg_breakdown(
    rows: Sequence[LegBreakdownInputRow],
    order_type_by_order_id: Mapping[str, str],
) -> ClosedTradeLegBreakdownResult:
    buy_c = 0
    sell_c = 0
    mkt = 0
    lim = 0
    oth = 0

    for r in rows:
        side_l = r.side.lower()
        if side_l == ORDER_SIDE_BUY:
            buy_c += 1
        elif side_l == ORDER_SIDE_SELL:
            sell_c += 1

        if side_l != ORDER_SIDE_SELL or r.realized_pnl_usd is None:
            continue

        oid = r.order_id
        if not oid:
            oth += 1
            continue

        ot = order_type_by_order_id.get(oid)
        if ot == ORDER_TYPE_MARKET:
            mkt += 1
        elif ot == ORDER_TYPE_LIMIT:
            lim += 1
        else:
            oth += 1

    return ClosedTradeLegBreakdownResult(
        trade_legs_buy_count=buy_c,
        trade_legs_sell_count=sell_c,
        closed_realized_sell_market_count=mkt,
        closed_realized_sell_limit_count=lim,
        closed_realized_sell_order_type_other_count=oth,
    )
