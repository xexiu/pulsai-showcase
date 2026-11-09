"""Behavior tests for :func:`compute_closed_trade_leg_breakdown` — leg counts + closed-sell order-type split."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.domain.services.closed_trade_leg_breakdown import (
    LegBreakdownInputRow,
    compute_closed_trade_leg_breakdown,
)
from src.shared.constants.paper_trading import (
    ORDER_SIDE_BUY,
    ORDER_SIDE_SELL,
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
)


def test_empty_rows_yields_zeros() -> None:
    out = compute_closed_trade_leg_breakdown((), {})
    assert out.trade_legs_buy_count == 0
    assert out.trade_legs_sell_count == 0
    assert out.closed_realized_sell_market_count == 0
    assert out.closed_realized_sell_limit_count == 0
    assert out.closed_realized_sell_order_type_other_count == 0


def test_counts_buy_and_sell_legs() -> None:
    rows = (
        LegBreakdownInputRow(side=ORDER_SIDE_BUY, order_id="o1", realized_pnl_usd=None),
        LegBreakdownInputRow(side=ORDER_SIDE_SELL, order_id="o2", realized_pnl_usd=None),
        LegBreakdownInputRow(side=ORDER_SIDE_BUY, order_id="o3", realized_pnl_usd=None),
    )
    out = compute_closed_trade_leg_breakdown(rows, {"o1": ORDER_TYPE_MARKET, "o2": ORDER_TYPE_LIMIT, "o3": ORDER_TYPE_MARKET})
    assert out.trade_legs_buy_count == 2
    assert out.trade_legs_sell_count == 1


def test_closed_realized_sells_split_by_parent_order_type() -> None:
    rows = (
        LegBreakdownInputRow(side=ORDER_SIDE_SELL, order_id="m1", realized_pnl_usd=Decimal(10)),
        LegBreakdownInputRow(side=ORDER_SIDE_SELL, order_id="l1", realized_pnl_usd=Decimal(-5)),
        LegBreakdownInputRow(side=ORDER_SIDE_SELL, order_id="l1", realized_pnl_usd=Decimal(2)),
    )
    types = {"m1": ORDER_TYPE_MARKET, "l1": ORDER_TYPE_LIMIT}
    out = compute_closed_trade_leg_breakdown(rows, types)
    assert out.closed_realized_sell_market_count == 1
    assert out.closed_realized_sell_limit_count == 2
    assert out.closed_realized_sell_order_type_other_count == 0


def test_sell_without_realized_does_not_count_as_closed_bucket() -> None:
    rows = (LegBreakdownInputRow(side=ORDER_SIDE_SELL, order_id="m1", realized_pnl_usd=None),)
    out = compute_closed_trade_leg_breakdown(rows, {"m1": ORDER_TYPE_MARKET})
    assert out.trade_legs_sell_count == 1
    assert out.closed_realized_sell_market_count == 0


def test_missing_order_id_or_unknown_type_goes_to_other() -> None:
    rows = (
        LegBreakdownInputRow(side=ORDER_SIDE_SELL, order_id=None, realized_pnl_usd=Decimal(1)),
        LegBreakdownInputRow(side=ORDER_SIDE_SELL, order_id="x", realized_pnl_usd=Decimal(1)),
    )
    out = compute_closed_trade_leg_breakdown(rows, {"x": "stop_loss"})
    assert out.closed_realized_sell_market_count == 0
    assert out.closed_realized_sell_limit_count == 0
    assert out.closed_realized_sell_order_type_other_count == 2


@pytest.mark.parametrize("side", ["BUY", "buy", "Buy"])
def test_side_matching_is_case_insensitive_for_buy(side: str) -> None:
    rows = (LegBreakdownInputRow(side=side, order_id=None, realized_pnl_usd=None),)
    out = compute_closed_trade_leg_breakdown(rows, {})
    assert out.trade_legs_buy_count == 1
