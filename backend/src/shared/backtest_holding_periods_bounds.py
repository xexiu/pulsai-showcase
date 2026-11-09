"""
Timeframe-aware max holding_periods for backtest requests.

Sub-hour (``BACKTEST_HOLDING_PERIODS_INTRADAY_TIMEFRAMES``): min(absolute ceiling, candles_per_day x calendar days).
Higher timeframes: legacy cap (100 candles).
"""

from __future__ import annotations

from src.shared.constants.backtest import (
    BACKTEST_HOLDING_PERIODS_ABSOLUTE_CEILING,
    BACKTEST_HOLDING_PERIODS_INTRADAY_TIMEFRAMES,
    BACKTEST_HOLDING_PERIODS_MAX,
    BACKTEST_MAX_HOLD_CALENDAR_DAYS,
)
from src.shared.constants.backtest_timeframe import (
    BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME,
    DEFAULT_BACKTEST_CANDLES_PER_DAY,
)


def resolve_backtest_holding_periods_max(timeframe: str) -> int:
    """Max candles allowed for holding_periods on the given timeframe."""
    normalized = (timeframe or "").strip().lower()

    if normalized not in BACKTEST_HOLDING_PERIODS_INTRADAY_TIMEFRAMES:
        return BACKTEST_HOLDING_PERIODS_MAX

    candles_per_day = BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME.get(
        normalized,
        DEFAULT_BACKTEST_CANDLES_PER_DAY,
    )
    calendar_cap = candles_per_day * BACKTEST_MAX_HOLD_CALENDAR_DAYS

    return min(BACKTEST_HOLDING_PERIODS_ABSOLUTE_CEILING, calendar_cap)


__all__ = ["resolve_backtest_holding_periods_max"]
