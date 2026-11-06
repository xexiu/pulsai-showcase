"""Shared helpers for backtester exit strategy modules."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
import polars as pl

from src.shared.constants.backtest_exit_types import (
    BACKTEST_EXIT_TYPE_STOP_LOSS,
    BACKTEST_EXIT_TYPE_TAKE_PROFIT,
    BACKTEST_EXIT_TYPE_TIMEOUT,
)


class PlannedExit(NamedTuple):
    """Where a trade leaves: its bar, the price it is booked at, the exit type -- and, when a resting stop closed it, the
    price that stop FILLED at on that bar. The position was not held past that fill, so the liquidation scan reads the
    exit bar there (LIQ-ONE); None = held through the whole bar. A multi-part exit (the thin-stop ladder) books a
    blended price, which is why the fill travels apart from it."""

    candle: int
    price: float
    exit_type: str
    stop_fill: float | None = None


def exit_at_levels(
    entry_candle: int,
    direction: int,
    df: pl.DataFrame,
    open_prices: np.ndarray,
    max_exit_candle: int,
    levels: tuple[float | None, float | None],
) -> PlannedExit:
    """First SL/TP hit at `levels`, or the timeout exit when a level is missing or never hit (fixed, ATR, dynamic)."""
    sl_level, tp_level = levels
    hit = None
    if sl_level is not None and tp_level is not None:
        hit = exit_on_first_hit(entry_candle, direction, df, max_exit_candle, sl_level, tp_level)
    return hit if hit is not None else timeout_signal_exit(max_exit_candle, open_prices, len(df))


def gap_fill(level: float, bar_open: float, *, worse_below: bool, gapped: bool) -> float:
    """Where a resting level fills on a bar that touched it: at the level, or at the bar's OPEN when the bar opened past
    it (``gapped`` bars only -- the entry bar's open is the entry). ``worse_below``: the open moved past the level from
    above (a long's stop / a short's target fill at the lower of the two), else from below (at the higher)."""
    if not gapped:
        return level
    return min(level, bar_open) if worse_below else max(level, bar_open)


def exit_on_first_hit(
    entry_candle: int,
    direction: int,
    df: pl.DataFrame,
    max_exit_candle: int,
    sl_level: float,
    tp_level: float,
) -> PlannedExit | None:
    """The first SL / TP hit in range, SL before TP (pessimistic) -- the thin-stop kernel's order. STOP-GAP: a level the
    bar OPENED past fills at that open (a gap through a stop costs the gap; a gap through a target pays it), and a stop
    exit carries its fill so the liquidation scan holds the exit bar only until it (LIQ-ONE)."""
    opens = df["open"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    long = direction == 1

    for candle in range(entry_candle, min(max_exit_candle + 1, len(df))):
        gapped = candle > entry_candle
        stop_hit = lows[candle] <= sl_level if long else highs[candle] >= sl_level
        if stop_hit:
            fill = gap_fill(sl_level, float(opens[candle]), worse_below=long, gapped=gapped)
            return PlannedExit(candle, fill, BACKTEST_EXIT_TYPE_STOP_LOSS, fill)
        target_hit = highs[candle] >= tp_level if long else lows[candle] <= tp_level
        if target_hit:
            fill = gap_fill(tp_level, float(opens[candle]), worse_below=not long, gapped=gapped)
            return PlannedExit(candle, fill, BACKTEST_EXIT_TYPE_TAKE_PROFIT)
    return None


def timeout_signal_exit(
    max_exit_candle: int,
    open_prices: np.ndarray,
    df_len: int,
) -> PlannedExit:
    """Force-close a barrier strategy at the ``holding_periods`` deadline.

    Returned by every barrier strategy (fixed_tpsl / risk_reward / atr_based /
    dynamic_tpsl / trailing_stop / min_profit) when no barrier triggered within the
    holding window. Labelled ``timeout`` -- NOT ``signal`` -- so exit-type attribution
    can distinguish a forced deadline exit from an intended FIXED_HOLDING exit.
    """
    exit_candle = min(max_exit_candle, df_len - 1)
    return PlannedExit(exit_candle, float(open_prices[exit_candle]), BACKTEST_EXIT_TYPE_TIMEOUT)
