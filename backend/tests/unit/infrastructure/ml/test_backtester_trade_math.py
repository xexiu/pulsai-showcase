"""Behavior tests for backtester trade math: the isolated-liquidation rule (LIQ-ONE, 2026-10-18).

A liquidation TRIGGERS at the liquidation price (the bankruptcy price moved in by the maintenance margin) and FILLS at
the bankruptcy price, so the position loses exactly its margin -- the exchange closes it there and the surplus goes to
the insurance fund. A resting stop that filled before the liquidation price on its own bar closed the position first.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.infrastructure.ml.backtester_trade_math import (
    calculate_trade_pnl,
    merge_planned_exit_with_intrabar_liquidation,
)
from src.shared.constants.backtest_leverage import BACKTEST_EXIT_TYPE_LIQUIDATION
from src.shared.math.linear_isolated_perp import (
    bankruptcy_price_linear_isolated,
    liquidation_price_linear_isolated_long,
    liquidation_price_linear_isolated_short,
)

_ENTRY = 100.0
_LEVERAGE = 10
_MMR = 0.004
_NOTIONAL = 1_000.0


def _merge(
    direction: int, low: list[float], high: list[float], planned: tuple[int, float, str], exit_bar_fill: float | None = None
) -> tuple[int, float, str, float | None]:
    return merge_planned_exit_with_intrabar_liquidation(
        fill_entry_candles=[0],
        fill_prices=[_ENTRY],
        direction=direction,
        leverage=_LEVERAGE,
        maintenance_margin_rate=_MMR,
        planned=planned,
        low_np=np.array(low),
        high_np=np.array(high),
        exit_bar_fill=exit_bar_fill,
    )


@pytest.mark.parametrize("direction", [1, -1])
def test_a_liquidated_position_loses_exactly_its_margin(direction: int) -> None:
    liq_px = (liquidation_price_linear_isolated_long if direction > 0 else liquidation_price_linear_isolated_short)(_ENTRY, _LEVERAGE, _MMR)
    low, high = ([99.0, liq_px - 0.1, 88.0], [101.0, 100.0, 90.0]) if direction > 0 else ([99.0, 100.0, 108.0], [101.0, liq_px + 0.1, 112.0])

    exit_candle, exit_price, exit_type, theoretical_liq = _merge(direction, low, high, (2, 95.0, "take_profit"))

    assert (exit_candle, exit_type) == (1, BACKTEST_EXIT_TYPE_LIQUIDATION)
    assert theoretical_liq == pytest.approx(liq_px)  # the trigger stays the maintenance-margin price
    assert exit_price == pytest.approx(bankruptcy_price_linear_isolated(_ENTRY, _LEVERAGE, direction))
    _gross, net, *_ = calculate_trade_pnl(_ENTRY, exit_price, direction, _NOTIONAL, 0.0, 0.0)
    assert net == pytest.approx(-_NOTIONAL / _LEVERAGE)  # the whole margin, not margin minus the maintenance part


def test_a_stop_that_filled_before_the_liquidation_price_on_its_own_bar_closed_the_position_first() -> None:
    liq_px = liquidation_price_linear_isolated_long(_ENTRY, _LEVERAGE, _MMR)
    stop = liq_px + 1.0  # closer to the entry than the liquidation price
    planned = (1, stop, "stop_loss")

    assert _merge(1, [99.0, liq_px - 2.0], [101.0, 100.0], planned, exit_bar_fill=stop) == (1, stop, "stop_loss", None)


def test_a_stop_that_gapped_past_the_liquidation_price_is_a_liquidation() -> None:
    liq_px = liquidation_price_linear_isolated_short(_ENTRY, _LEVERAGE, _MMR)
    gap_open = liq_px + 0.5  # the bar opened beyond the liquidation price, so the stop filled there
    planned = (1, gap_open, "stop_loss")

    exit_candle, _price, exit_type, _liq = _merge(-1, [99.0, 100.0], [101.0, liq_px + 1.0], planned, exit_bar_fill=gap_open)

    assert (exit_candle, exit_type) == (1, BACKTEST_EXIT_TYPE_LIQUIDATION)


def test_without_a_stop_fill_the_exit_bar_is_read_at_its_extreme() -> None:
    liq_px = liquidation_price_linear_isolated_long(_ENTRY, _LEVERAGE, _MMR)

    exit_candle, _price, exit_type, _liq = _merge(1, [99.0, liq_px - 0.1], [101.0, 100.0], (1, 99.0, "signal"))

    assert (exit_candle, exit_type) == (1, BACKTEST_EXIT_TYPE_LIQUIDATION)


def test_a_dca_liquidation_fills_at_the_bankruptcy_price_of_the_average_in_force() -> None:
    fills = [100.0, 96.0]
    liq_first = liquidation_price_linear_isolated_long(100.0, _LEVERAGE, _MMR)
    low = np.array([99.0, liq_first - 0.1, 95.0, 95.0])  # bar 1 liquidates the first fill before the second arrives
    high = np.full(4, 101.0)

    exit_candle, exit_price, exit_type, _liq = merge_planned_exit_with_intrabar_liquidation(
        [0, 2], fills, 1, _LEVERAGE, _MMR, (3, 99.0, "take_profit"), low, high
    )

    assert (exit_candle, exit_type) == (1, BACKTEST_EXIT_TYPE_LIQUIDATION)
    assert exit_price == pytest.approx(bankruptcy_price_linear_isolated(100.0, _LEVERAGE, 1))


def test_merge_spot_skips_liquidation_even_when_wick_would_cross() -> None:
    result = merge_planned_exit_with_intrabar_liquidation(
        fill_entry_candles=[0],
        fill_prices=[100.0],
        direction=1,
        leverage=0,
        maintenance_margin_rate=0.004,
        planned=(2, 95.0, "holding"),
        low_np=np.array([50.0, 50.0, 50.0]),
        high_np=np.array([150.0, 150.0, 150.0]),
    )

    assert result == (2, 95.0, "holding", None)
