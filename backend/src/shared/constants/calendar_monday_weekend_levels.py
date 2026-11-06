"""
SoT for calendar Monday / weekend high-low feature columns and UTC weekday rules.

Polars ``dt.weekday()``: Monday=1, Sunday=7 (see Polars temporal docs).
"""

from __future__ import annotations

# Epoch values >= this are treated as milliseconds; else seconds.
EPOCH_MS_THRESHOLD: float = 1e12

# Polars UTC weekday indices (Monday=1, Saturday=6, Sunday=7).
POLARS_MONDAY_WEEKDAY: int = 1
POLARS_SATURDAY_WEEKDAY: int = 6
POLARS_SUNDAY_WEEKDAY: int = 7
POLARS_WEEKEND_WEEKDAYS: tuple[int, ...] = (POLARS_SATURDAY_WEEKDAY, POLARS_SUNDAY_WEEKDAY)

# ISO year-week key for calendar-week Monday levels.
ISO_YEAR_WEEK_FORMAT: str = "%G-%V"

# Feature columns produced by ``add_calendar_monday_weekend_levels``.
CALENDAR_MONDAY_WEEKEND_COLUMNS: tuple[str, ...] = (
    "high_monday",
    "low_monday",
    "high_weekend",
    "low_weekend",
)

# Sentinel when no Monday/weekend level exists yet (chart hides 0 via FE plottable checks).
CALENDAR_LEVEL_UNSET: float = 0.0

# Chart display TF → OHLCV TF used to compute calendar Monday/weekend levels (HTF projection).
# 1w bars never land on Sat/Sun; derive weekend session from daily UTC bars instead.
CHART_CALENDAR_LEVEL_SOURCE_TIMEFRAME: dict[str, str] = {"1w": "1d"}

# Cap for chart-indicators / market OHLCV ``limit`` query (must match FE
# ``MARKET_OHLCV_API_MAX_CANDLES``). Sized for two weeks of 5m bars (14 x 288 = 4032).
MARKET_CHART_OHLCV_MAX_LIMIT: int = 4500

# Extra daily bars beyond ``weekly_limit * 7`` for warmup / partial weeks.
CALENDAR_DAILY_LIMIT_BUFFER_BARS: int = 14
