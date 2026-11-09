"""Apply SL/TP levels to a trade after entry (extracted from CryptoBacktester for file-size SRP)."""

from __future__ import annotations

import math
from typing import Protocol

import polars as pl

from src.infrastructure.ml.backtester_types import ExitStrategy, Trade


class _BacktesterTradeLevelOps(Protocol):
    exit_strategy: ExitStrategy

    def _dynamic_entry_metadata(
        self,
        entry_price: float,
        direction: int,
        df: pl.DataFrame,
        entry_candle: int,
    ) -> tuple[float | None, float | None, str | None]: ...

    def _compute_tpsl_levels(
        self,
        entry_price: float,
        direction: int,
        df: pl.DataFrame,
        signal_bar: int,
    ) -> tuple[float | None, float | None]: ...


def _safe_float(value: object) -> float | None:
    """A finite float from a row cell, or None: a missing or non-numeric cell is an absent level here, not an error."""
    parsed = math.nan
    if isinstance(value, int | float | str):
        try:
            parsed = float(value)
        except ValueError:  # a non-numeric string; ints, floats and numeric strings all parse
            parsed = math.nan
    return parsed if math.isfinite(parsed) else None


def _is_valid_profit_target(direction: int, entry_price: float, level_price: float) -> bool:
    return level_price > entry_price if direction == 1 else level_price < entry_price


def _derive_tp_bands(
    *,
    trade: Trade,
    df: pl.DataFrame,
    signal_bar_index: int,
) -> tuple[float | None, float | None, float | None]:
    stop_loss = trade.stop_loss_price
    take_profit = trade.take_profit_price
    if stop_loss is None or take_profit is None:
        return None, None, None

    direction = 1 if trade.direction >= 0 else -1
    risk_abs = abs(trade.entry_price - stop_loss)
    if risk_abs <= 0:
        return None, None, None

    tp_half = trade.entry_price + (direction * risk_abs * 0.5)
    tp_1r: float | None = trade.entry_price + (direction * risk_abs)
    tp_candidate_1 = take_profit
    if direction == 1 and tp_candidate_1 < tp_half:
        tp_candidate_1 = tp_half
    if direction == -1 and tp_candidate_1 > tp_half:
        tp_candidate_1 = tp_half

    entry_candle_index = signal_bar_index + 1
    row = df.row(entry_candle_index, named=True) if entry_candle_index < len(df) else {}
    channel_key = "channel_5m_upper" if direction == 1 else "channel_5m_lower"
    channel_level = _safe_float(row.get(channel_key))
    channel_valid = channel_level is not None and _is_valid_profit_target(direction, trade.entry_price, channel_level)

    min_tp: float | None
    full_tp: float | None
    if channel_valid and channel_level is not None:
        min_tp = min(tp_candidate_1, channel_level) if direction == 1 else max(tp_candidate_1, channel_level)
        full_tp = max(tp_candidate_1, channel_level) if direction == 1 else min(tp_candidate_1, channel_level)
        if full_tp == min_tp:
            full_tp = None
    else:
        min_tp = tp_candidate_1
        vol_margin = _safe_float(row.get("volatility_margin"))
        full_tp = min_tp + (direction * vol_margin * 2.0) if vol_margin is not None and vol_margin > 0 else None

    if min_tp is not None and not _is_valid_profit_target(direction, trade.entry_price, min_tp):
        min_tp = None
    if tp_1r is not None and not _is_valid_profit_target(direction, trade.entry_price, tp_1r):
        tp_1r = None
    if full_tp is not None and not _is_valid_profit_target(direction, trade.entry_price, full_tp):
        full_tp = None

    return min_tp, tp_1r, full_tp


def apply_trade_levels_for_signal_bar(
    backtester: _BacktesterTradeLevelOps,
    trade: Trade,
    df: pl.DataFrame,
    *,
    signal_bar_index: int,
) -> None:
    """Set ``trade`` stop/take from dynamic or fixed pipeline at signal bar context.

    The ATR candle is the SIGNAL bar -- the last closed bar when the trade fills at the next open -- so the stamped levels
    are the ones the exit actually used (check_dynamic_tpsl_exit / check_atr_tpsl_exit size from `entry_candle - 1`).
    """
    sl: float | None = None
    tp: float | None = None
    dynamic = backtester.exit_strategy == ExitStrategy.DYNAMIC_TPSL
    if not dynamic:
        sl, tp = backtester._compute_tpsl_levels(trade.entry_price, trade.direction, df, signal_bar_index)
        dynamic = sl is None and tp is None  # a fixed pipeline that defines no level falls back to the dynamic one
    if dynamic:
        sl, tp, trade.dynamic_volatility_regime = backtester._dynamic_entry_metadata(trade.entry_price, trade.direction, df, signal_bar_index)
    trade.stop_loss_price = sl
    trade.take_profit_price = tp
    trade.min_tp_price, trade.tp_1r_price, trade.full_tp_price = _derive_tp_bands(trade=trade, df=df, signal_bar_index=signal_bar_index)


__all__ = ["apply_trade_levels_for_signal_bar"]
