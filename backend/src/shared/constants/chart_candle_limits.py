"""The candle `limit` the CHART actually asks for, so the server can warm those exact keys.

WHY THIS EXISTS (measured on prod, 2026-09-06). `GET /market/chart-indicators` caches a fully
assembled response keyed by `(symbol, tf, limit, last_closed_bar_ts, enabled_indicators, ...)`.
A key nobody has warmed costs the user the whole pipeline:

    chart-indicators 5m/4032 COLD .... 1308 ms   (703 KB)
    chart-indicators 5m/4032 warm ....  397 ms
    chart-indicators 15m/1344 COLD ...  584 ms
    market/ohlcv     5m/4032 COLD ....  475 ms

Prod paged `endpoint /api/v1/market/chart-indicators [5m] critical p95=1.269s` while a real user
was reading charts, and 1308 ms is that number. Warming removes ~900 ms of it.

THE LIMIT IS NOT A CONSTANT, which is why a warmer cannot guess it. The front end derives it per
timeframe in `apps/web/src/utils/chart-time/limits.ts::getFullChartCandleFetchLimit`:

    limit(tf) = min(max(FLOOR, bars_per_day(tf) * history_days(tf)), MAX)

and the history window is 14 days on the low intraday timeframes rather than 2, which is the
whole reason 5m lands at 4032 while everything from 1h up lands on the 500 floor:

    5m -> 4032    15m -> 1344    30m -> 672    1h..1d -> 500

Warming `limit=500` for 5m would warm a key no client ever requests, and the user would still pay
1308 ms. That is why this module reproduces the FE's rule instead of picking a number.

WHAT IS DERIVED AND WHAT IS MIRRORED. Only three values are mirrored -- the floor and the two
history windows. Everything else is already server-owned and is IMPORTED, not copied:

    bars_per_day()                 src.shared.constants.timeframes  (registry delta, not a map)
    MARKET_CHART_OHLCV_MAX_LIMIT   src.shared.constants.calendar_monday_weekend_levels

A mirror kept in step by a comment always drifts -- `MARKET_CHART_OHLCV_MAX_LIMIT` already carries
"(must match FE ``MARKET_OHLCV_API_MAX_CANDLES``)" and nothing checked it. So the three mirrored
values, AND that pre-existing one, are pinned by `test_chart_candle_limits_match_the_frontend`,
which parses the TypeScript and fails on disagreement. The test is the mechanism; this docstring
is not.

THE SERVER IS NOW THE SOURCE. `GET /api/v1/config/public` publishes `chart_candle_limit` on every
`TimeframePublicOption`, beside the `ms` that already comes from TIMEFRAME_REGISTRY. So the value
the chart should request is served, not re-derived, and this module is what computes it.

The front end still computes its own copy until it is switched over to consume that field, which
is why the drift test exists and why it is not optional: for as long as two implementations are
live, the only thing standing between them and a silent disagreement is a test that reads both.
When the FE consumes the served value, the three mirrored constants below can be deleted outright
and the test with them.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from src.shared.constants.calendar_monday_weekend_levels import MARKET_CHART_OHLCV_MAX_LIMIT
from src.shared.constants.timeframes import bars_per_day

__all__ = [
    "CHART_LOWER_TF_MIN_HISTORY_DAYS",
    "CHART_MIN_HISTORY_DAYS",
    "FULL_CHART_CANDLE_FLOOR",
    "TIMEFRAME_HISTORY_DAYS_OVERRIDES",
    "full_chart_candle_limit",
]

#: Minimum visible history for timeframes without an override. Mirrors FE `CHART_MIN_HISTORY_DAYS`.
CHART_MIN_HISTORY_DAYS: Final[int] = 2

#: Low intraday timeframes get a deeper window for multi-session context. Mirrors FE
#: `CHART_LOWER_TF_MIN_HISTORY_DAYS`. This is what makes 5m cost 4032 candles.
CHART_LOWER_TF_MIN_HISTORY_DAYS: Final[int] = 14

#: Per-timeframe history floor in days. Mirrors FE `TIMEFRAME_HISTORY_DAYS_OVERRIDES`.
TIMEFRAME_HISTORY_DAYS_OVERRIDES: Final[Mapping[str, int]] = {
    "5m": CHART_LOWER_TF_MIN_HISTORY_DAYS,
    "15m": CHART_LOWER_TF_MIN_HISTORY_DAYS,
    "30m": CHART_LOWER_TF_MIN_HISTORY_DAYS,
}

#: Floor so hourly-and-coarser charts still load a deep window. Mirrors FE
#: `FULL_CHART_CANDLE_FLOOR`, which is module-private on that side.
FULL_CHART_CANDLE_FLOOR: Final[int] = 500


def full_chart_candle_limit(timeframe: str) -> int:
    """The `limit` the chart requests for ``timeframe``.

    Mirrors `getFullChartCandleFetchLimit`. Raises on an unknown timeframe rather than defaulting,
    because `bars_per_day` does -- a silent per-timeframe default is exactly what makes this class
    of drift invisible.
    """
    key = timeframe.strip().lower()
    history_days = TIMEFRAME_HISTORY_DAYS_OVERRIDES.get(key, CHART_MIN_HISTORY_DAYS)
    for_history = int(bars_per_day(key) * history_days)
    return min(max(FULL_CHART_CANDLE_FLOOR, for_history), MARKET_CHART_OHLCV_MAX_LIMIT)
