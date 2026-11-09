"""Tests for CCXT order leverage extraction (Historial APAL / DB persistence)."""

from __future__ import annotations

from src.domain.services.ccxt_order_leverage_extract import (
    extract_leverage_int_from_ccxt_order,
    leverage_for_db_from_ccxt_response,
)
from src.shared.constants.exchanges import MARKET_TYPE_SWAP


def test_extract_top_level_leverage() -> None:
    assert extract_leverage_int_from_ccxt_order({"leverage": 12}) == 12
    assert extract_leverage_int_from_ccxt_order({"leverage": "5"}) == 5


def test_extract_from_info_bitget_style_keys() -> None:
    assert extract_leverage_int_from_ccxt_order({"info": {"holdLeverage": "3"}}) == 3
    assert extract_leverage_int_from_ccxt_order({"info": {"leverage": 10}}) == 10


def test_swap_prefers_venue_over_placement() -> None:
    assert (
        leverage_for_db_from_ccxt_response(
            market_type=MARKET_TYPE_SWAP,
            ccxt_order={"leverage": 20},
            placement_leverage=3,
        )
        == 20
    )


def test_swap_falls_back_to_placement_when_no_venue_field() -> None:
    assert (
        leverage_for_db_from_ccxt_response(
            market_type=MARKET_TYPE_SWAP,
            ccxt_order={"id": "x", "info": {}},
            placement_leverage=7,
        )
        == 7
    )


def test_spot_ignores_ccxt_leverage() -> None:
    assert (
        leverage_for_db_from_ccxt_response(
            market_type="spot",
            ccxt_order={"leverage": 99},
            placement_leverage=None,
        )
        is None
    )
