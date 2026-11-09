"""DCA piecewise-liquidation guard (2026-07-10).

A scaled-in (DCA) position's liquidation price moves each time the weighted-average
entry moves. The old code scanned the whole holding span against ONE final-average
liq price, under-detecting early liquidations that would have fired on the then-current
(closer) average — making leveraged DCA look safer than reality. The piecewise scan
walks each inter-fill segment against the liq price actually in force during it.
"""

from __future__ import annotations

import numpy as np

from src.infrastructure.ml.backtester_trade_math import merge_planned_exit_with_intrabar_liquidation
from src.shared.constants.backtest_leverage import BACKTEST_EXIT_TYPE_LIQUIDATION
from src.shared.math.linear_isolated_perp import liquidation_price_linear_isolated_long

LEV = 5
MMR = 0.004


def _arrays(n: int, default_low: float = 500.0) -> tuple[np.ndarray, np.ndarray]:
    return np.full(n, default_low), np.full(n, 500.0)


def test_piecewise_catches_early_liquidation_that_final_avg_scan_misses() -> None:
    """Long DCA: fill @100 (c10) then avg-down @80 (c12). Between fills (c11) price dips
    to 79 — below the 1-leg liq (~80.4) but above the 2-leg final-avg liq (~72.4)."""
    liq_1leg = liquidation_price_linear_isolated_long(100.0, LEV, MMR)  # ~80.4
    liq_2leg = liquidation_price_linear_isolated_long(90.0, LEV, MMR)  # ~72.4 (avg of 100,80)
    assert liq_2leg < 79.0 < liq_1leg  # the whole point: 79 is between the two liq prices

    low, high = _arrays(25)
    low[11] = 79.0  # 1-leg segment [10,11] — should liquidate here
    low[12:21] = 85.0  # 2-leg segment — safely above liq_2leg
    planned = (20, 95.0, "timeout")

    # NEW piecewise scan: liquidates at candle 11 on the 1-leg average.
    cand, _px, etype, liqpx = merge_planned_exit_with_intrabar_liquidation(
        [10, 12],
        [100.0, 80.0],
        1,
        LEV,
        MMR,
        planned,
        low,
        high,
    )
    assert etype == BACKTEST_EXIT_TYPE_LIQUIDATION
    assert cand == 11
    assert liqpx is not None
    assert abs(liqpx - liq_1leg) < 1e-6

    # OLD single-average scan (final avg 90) MISSES it → returns the planned timeout.
    old = merge_planned_exit_with_intrabar_liquidation(
        [10],
        [90.0],
        1,
        LEV,
        MMR,
        planned,
        low,
        high,
    )
    assert old[2] == "timeout"  # under-detection: the bug this fix closes


def test_piecewise_reduces_to_single_scan_for_one_fill() -> None:
    low, high = _arrays(20)
    liq = liquidation_price_linear_isolated_long(100.0, LEV, MMR)
    low[15] = liq - 0.5
    cand, _px, etype, _liq = merge_planned_exit_with_intrabar_liquidation(
        [10],
        [100.0],
        1,
        LEV,
        MMR,
        (18, 105.0, "timeout"),
        low,
        high,
    )
    assert etype == BACKTEST_EXIT_TYPE_LIQUIDATION
    assert cand == 15


def test_piecewise_no_liquidation_returns_planned() -> None:
    low, high = _arrays(20)  # never dips
    out = merge_planned_exit_with_intrabar_liquidation(
        [10, 13],
        [100.0, 90.0],
        1,
        LEV,
        MMR,
        (18, 110.0, "take_profit"),
        low,
        high,
    )
    assert out[0] == 18
    assert out[2] == "take_profit"
