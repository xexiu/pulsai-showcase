"""Behavior tests for the leverage-aware SL cap (P1.1b).

A stop-loss can only trigger if it sits INSIDE the liquidation band: at 100x you're liquidated
at ~1%, so an 8% stop never fires. The cap encodes that, and the grid filter drops such profiles
from a leveraged sweep (SL side only — TP is a favorable move, never capped).
"""

from __future__ import annotations

from src.infrastructure.ml.exit_grid import build_fifo_oos_exit_grid, filter_exit_grid_for_leverage
from src.shared.constants.backtest_leverage import max_sl_pct_for_leverage

_HIGH_LEVERAGE = 100
_MID_LEVERAGE = 3


def test_no_cap_for_spot_or_1x() -> None:
    assert max_sl_pct_for_leverage(0) is None
    assert max_sl_pct_for_leverage(1) is None


def test_8pct_stop_fits_at_3x_but_not_100x() -> None:
    cap_3x = max_sl_pct_for_leverage(_MID_LEVERAGE)
    cap_100x = max_sl_pct_for_leverage(_HIGH_LEVERAGE)
    assert cap_3x is not None
    assert cap_3x > 8.0  # 8% stop is valid at 3x
    assert cap_100x is not None
    assert cap_100x < 1.0  # ~0.5% -> an 8% stop is impossible at 100x


def test_cap_tightens_monotonically_with_leverage() -> None:
    caps = [max_sl_pct_for_leverage(lv) for lv in (2, 5, 10, 50, 100)]
    assert all(c is not None for c in caps)
    assert caps == sorted(caps, reverse=True)  # higher leverage -> smaller cap


def test_filter_leaves_spot_grid_unchanged() -> None:
    grid = build_fifo_oos_exit_grid()
    assert filter_exit_grid_for_leverage(grid, 0) == grid


def test_filter_drops_impossible_stops_at_high_leverage_keeps_them_at_3x() -> None:
    grid = build_fifo_oos_exit_grid()
    cap_100x = max_sl_pct_for_leverage(_HIGH_LEVERAGE)
    assert cap_100x is not None

    filtered_100x = filter_exit_grid_for_leverage(grid, _HIGH_LEVERAGE)
    # every survivor has no SL, or an SL within the 100x cap
    assert all(float(p.hub_fields.get("stop_loss_pct") or 0.0) <= cap_100x for p in filtered_100x)
    # the 8%/8% tpsl profile cannot exist at 100x...
    assert not any(p.hub_fields.get("stop_loss_pct") == 8.0 for p in filtered_100x)
    # ...but is retained at 3x
    filtered_3x = filter_exit_grid_for_leverage(grid, _MID_LEVERAGE)
    assert any(p.hub_fields.get("stop_loss_pct") == 8.0 for p in filtered_3x)
