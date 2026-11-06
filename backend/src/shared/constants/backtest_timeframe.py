"""
Timeframe SoT for backtest annualization, trade-frequency warnings, and candles/day.

Why centralized:
- `CryptoBacktester`, `backtester_metrics.calculate_metrics`, and `monte_carlo` used
  divergent or duplicated dicts (DRY + numeric parity for Sharpe annualization / HF warnings).
"""

from __future__ import annotations

from typing import Final

from src.shared.constants.timeframes import TIMEFRAME_MS

# Default when timeframe is unknown: same as legacy 1h periods/year (trades_yearly scaling).
DEFAULT_BACKTEST_PERIODS_PER_YEAR: Final[int] = 8_760

_MINUTES_PER_DAY: Final[int] = 24 * 60
_DAYS_PER_YEAR: Final[int] = 365


def _timeframe_minutes(timeframe: str) -> float:
    return TIMEFRAME_MS[timeframe] / 60_000.0


# Trading minutes per year (60 * 24 * 365) for bar counts; used for Sharpe/Sortino annualization.
#
# DERIVED from TIMEFRAME_MS rather than hand-typed. These were a literal dict that silently lost
# 2h and 6h when the registry gained them (owner spotted the same class of gap in
# packages/shared on 2026-08-13), and a MISSING annualization divisor is not a crash — the caller
# falls back to DEFAULT_BACKTEST_PERIODS_PER_YEAR, i.e. the 1h value, so a 6h book's Sharpe would
# be annualized as if it traded six times as often. Deriving reproduces every previous entry
# exactly (verified against the old literals in the test) and cannot fall behind again.
BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME: Final[dict[str, int]] = {
    timeframe: round(_MINUTES_PER_DAY * _DAYS_PER_YEAR / _timeframe_minutes(timeframe)) for timeframe in TIMEFRAME_MS
}

# Candles per calendar day (for “trades per day” and HF warning denominators).
# Floored at 1 so multi-day bars (3d, 1w) stay a valid denominator.
BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME: Final[dict[str, int]] = {
    timeframe: max(1, round(_MINUTES_PER_DAY / _timeframe_minutes(timeframe))) for timeframe in TIMEFRAME_MS
}

# “High frequency” = trades per day above this threshold (by timeframe, product tuning).
BACKTEST_HIGH_FREQUENCY_TRADES_PER_DAY_THRESHOLD: Final[dict[str, int]] = {
    "1m": 100,
    "5m": 50,
    "15m": 20,
    "30m": 10,
    "1h": 5,
    # 2h/6h interpolated on candles-per-day, which is what this threshold tracks: 1h has 24
    # candles/day at 5, 4h has 6 at 3, 8h has 3 at 2. Product tuning, so NOT derived like the two
    # maps above — a judgement call belongs in a literal where it can be argued with.
    "2h": 4,
    "4h": 3,
    "6h": 2,
    "8h": 2,
    "12h": 2,
    "1d": 1,
    "3d": 1,
    "1w": 1,
}

DEFAULT_BACKTEST_HIGH_FREQ_THRESHOLD: Final[int] = 5
DEFAULT_BACKTEST_CANDLES_PER_DAY: Final[int] = 24

__all__ = [
    "BACKTEST_CANDLES_PER_DAY_BY_TIMEFRAME",
    "BACKTEST_HIGH_FREQUENCY_TRADES_PER_DAY_THRESHOLD",
    "BACKTEST_PERIODS_PER_YEAR_BY_TIMEFRAME",
    "DEFAULT_BACKTEST_CANDLES_PER_DAY",
    "DEFAULT_BACKTEST_HIGH_FREQ_THRESHOLD",
    "DEFAULT_BACKTEST_PERIODS_PER_YEAR",
]
