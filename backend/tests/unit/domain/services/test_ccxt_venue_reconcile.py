"""Venue reconcile: post-create_order fetch_order + fetch_positions snapshot and public flattening."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.ccxt_venue_reconcile import (
    VENUE_MERGED_PUBLIC_API_FIELD_KEYS,
    flatten_venue_futures_hints_from_ccxt_order,
    flatten_venue_position_to_public_fields,
    merged_venue_public_from_reconcile_snap,
    pick_primary_unified_position,
)
from src.shared.constants.exchanges import MARKET_TYPE_SPOT, MARKET_TYPE_SWAP


def test_pick_primary_prefers_non_zero_contracts_same_symbol() -> None:
    positions = [
        {"symbol": "BTC/USDT:USDT", "contracts": 0, "side": "long"},
        {"symbol": "BTC/USDT:USDT", "contracts": 0.01, "side": "long", "markPrice": 100},
    ]
    got = pick_primary_unified_position(positions, "BTC/USDT:USDT")
    assert got is not None
    assert got.get("contracts") == 0.01


def test_pick_primary_returns_none_when_flat() -> None:
    positions = [{"symbol": "BTC/USDT:USDT", "contracts": 0, "side": "long"}]
    assert pick_primary_unified_position(positions, "BTC/USDT:USDT") is None


def test_flatten_drops_implausible_positive_outlier_vs_mark() -> None:
    pos = {
        "symbol": "BTC/USDT:USDT",
        "contracts": 0.01,
        "markPrice": 82000.0,
        "liquidationPrice": "7446261.22",
    }
    flat = flatten_venue_position_to_public_fields(pos)
    assert flat["venue_liquidation_price"] is None


def test_flatten_drops_implausible_negative_liquidation_price() -> None:
    """Bitget shows no est. liq. (--); CCXT may still populate garbage ``liquidationPrice``."""
    pos = {
        "symbol": "BTC/USDT:USDT",
        "contracts": 0.01,
        "markPrice": 82000.0,
        "liquidationPrice": "-7446261.22",
    }
    flat = flatten_venue_position_to_public_fields(pos)
    assert flat["venue_liquidation_price"] is None


def test_merged_order_hint_fills_liq_when_position_value_dropped() -> None:
    pos = {
        "symbol": "BTC/USDT:USDT",
        "contracts": 0.01,
        "markPrice": 82000.0,
        "liquidationPrice": "-7446261.22",
    }
    order = {"info": {"liquidationPrice": "50100.5"}}
    snap = {"ccxt_order": order, "ccxt_positions": [pos]}
    merged = merged_venue_public_from_reconcile_snap(snap, order_symbol="BTC/USDT:USDT")
    assert merged["venue_liquidation_price"] == "50100.5"


def test_flatten_maps_ccxt_unified_position() -> None:
    pos = {
        "symbol": "BTC/USDT:USDT",
        "entryPrice": 76000.0,
        "markPrice": 76100.5,
        "liquidationPrice": 50000.0,
        "initialMargin": 25.3,
        "unrealizedPnl": 1.25,
        "marginMode": "cross",
        "realizedPnl": -0.0592,
        "percentage": -0.84,
        "maintenanceMarginPercentage": 0.004,
    }
    flat = flatten_venue_position_to_public_fields(pos)
    assert flat["venue_entry_price"] == "76000"
    assert flat["venue_mark_price"] == "76100.5"
    assert flat["venue_liquidation_price"] == "50000"
    assert flat["venue_initial_margin"] == "25.3"
    assert flat["venue_unrealized_pnl"] == "1.25"
    assert flat["venue_margin_mode"] == "cross"
    assert flat["venue_realized_pnl"] == "-0.0592"
    assert flat["venue_roe_pct"] == "-0.84"
    assert flat["venue_maintenance_margin_rate"] == "0.004"
    assert flat["venue_breakeven_price"] is None


def test_flatten_reads_bitget_break_even_from_info() -> None:
    """Bitget puts breakEvenPrice on raw position blob under ``info`` (see CCXT bitget.parse_position)."""
    pos = {
        "symbol": "BTC/USDT:USDT",
        "contracts": 0.01,
        "marginMode": "cross",
        "entryPrice": 76018.7,
        "info": {
            "breakEvenPrice": "76110.0",
            "marginMode": "crossed",
        },
    }
    flat = flatten_venue_position_to_public_fields(pos)
    assert flat["venue_breakeven_price"] == "76110"
    assert flat["venue_margin_mode"] == "cross"


def test_flatten_empty_when_no_position() -> None:
    flat = flatten_venue_position_to_public_fields(None)
    assert all(v is None for v in flat.values())


def test_flatten_emits_exactly_api_field_keys() -> None:
    flat = flatten_venue_position_to_public_fields(None)
    assert tuple(sorted(flat.keys())) == tuple(sorted(VENUE_MERGED_PUBLIC_API_FIELD_KEYS))


def test_merged_venue_public_emits_exactly_api_field_keys() -> None:
    snap = {"ccxt_order": {"status": "closed"}, "ccxt_positions": []}
    merged = merged_venue_public_from_reconcile_snap(snap, order_symbol="BTC/USDT:USDT")
    assert tuple(sorted(merged.keys())) == tuple(sorted(VENUE_MERGED_PUBLIC_API_FIELD_KEYS))


def test_flatten_order_reads_bitget_info_liq_and_break_even() -> None:
    order = {
        "id": "x",
        "info": {
            "breakEvenPrice": "76200.25",
            "liquidationPrice": "50123.4",
        },
    }
    flat = flatten_venue_futures_hints_from_ccxt_order(order)
    assert flat["venue_breakeven_price"] == "76200.25"
    assert flat["venue_liquidation_price"] == "50123.4"


def test_merged_fills_breakeven_from_order_when_position_missing_it() -> None:
    pos = {
        "symbol": "BTC/USDT:USDT",
        "contracts": 0.01,
        "entryPrice": 76000.0,
        "markPrice": 76100.0,
        "liquidationPrice": 50000.0,
        "marginMode": "cross",
    }
    order = {"id": "o1", "info": {"breakEvenPrice": "76050.5"}}
    snap = {"ccxt_order": order, "ccxt_positions": [pos]}
    merged = merged_venue_public_from_reconcile_snap(snap, order_symbol="BTC/USDT:USDT")
    assert merged["venue_liquidation_price"] == "50000"
    assert merged["venue_breakeven_price"] == "76050.5"


def test_merged_prefers_position_values_over_order_when_both_present() -> None:
    pos = {
        "symbol": "BTC/USDT:USDT",
        "contracts": 0.01,
        "liquidationPrice": 50000.0,
        "info": {"breakEvenPrice": "76100"},
    }
    order = {"info": {"liquidationPrice": "1", "breakEvenPrice": "2"}}
    snap = {"ccxt_order": order, "ccxt_positions": [pos]}
    merged = merged_venue_public_from_reconcile_snap(snap, order_symbol="BTC/USDT:USDT")
    assert merged["venue_liquidation_price"] == "50000"
    assert merged["venue_breakeven_price"] == "76100"


@pytest.mark.asyncio
async def test_fetch_venue_reconcile_snapshot_swap_calls_order_and_positions() -> None:
    import ccxt.async_support as ccxt

    from src.domain.services.ccxt_venue_reconcile import fetch_venue_reconcile_snapshot

    ex = MagicMock(spec=ccxt.Exchange)
    ex.fetch_order = AsyncMock(return_value={"id": "o1", "status": "closed"})
    ex.fetch_positions = AsyncMock(return_value=[{"symbol": "BTC/USDT:USDT", "contracts": 0.01, "side": "long"}])

    snap = await fetch_venue_reconcile_snapshot(
        ex,
        unified_symbol="BTC/USDT:USDT",
        market_type=MARKET_TYPE_SWAP,
        ccxt_order_id="o1",
    )
    assert snap is not None
    assert snap["ccxt_order"]["id"] == "o1"
    assert len(snap["ccxt_positions"]) == 1
    ex.fetch_order.assert_awaited_once_with("o1", "BTC/USDT:USDT")
    ex.fetch_positions.assert_awaited_once_with(["BTC/USDT:USDT"])


@pytest.mark.asyncio
async def test_fetch_venue_reconcile_snapshot_swap_flat_book_without_order_id() -> None:
    """Lifecycle calls with ``ccxt_order_id=None`` must still observe a flat venue (empty positions)."""
    import ccxt.async_support as ccxt

    from src.domain.services.ccxt_venue_reconcile import fetch_venue_reconcile_snapshot

    ex = MagicMock(spec=ccxt.Exchange)
    ex.fetch_positions = AsyncMock(return_value=[])

    snap = await fetch_venue_reconcile_snapshot(
        ex,
        unified_symbol="BTC/USDT:USDT",
        market_type=MARKET_TYPE_SWAP,
        ccxt_order_id=None,
    )
    assert snap is not None
    assert snap["ccxt_order"] is None
    assert snap["ccxt_positions"] == []
    ex.fetch_positions.assert_awaited_once_with(["BTC/USDT:USDT"])


@pytest.mark.asyncio
async def test_fetch_venue_reconcile_snapshot_spot_skips_positions() -> None:
    import ccxt.async_support as ccxt

    from src.domain.services.ccxt_venue_reconcile import fetch_venue_reconcile_snapshot

    ex = MagicMock(spec=ccxt.Exchange)
    ex.fetch_order = AsyncMock(return_value={"id": "x", "status": "closed"})
    ex.fetch_positions = AsyncMock()

    snap = await fetch_venue_reconcile_snapshot(
        ex,
        unified_symbol="BTC/USDT",
        market_type=MARKET_TYPE_SPOT,
        ccxt_order_id="x",
    )
    assert snap is not None
    assert snap["ccxt_positions"] == []
    ex.fetch_positions.assert_not_called()
