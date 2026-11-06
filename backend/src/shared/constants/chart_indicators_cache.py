"""SoT for the pre-computed chart-indicators payload cache (J4).

Empirical context (2026-06-01)
------------------------------
Baseline benchmarks against ``FastFeatureCalculator.calculate_all`` show
indicator compute is the dominant cost of the chart-indicators endpoint:

* ``limit=500``  → p95 246ms, p99 305ms  (misses the 200ms SLO)
* ``limit=864``  → p95 200ms, p99 201ms  (right at SLO ceiling)
* ``limit=2000`` → p95 445ms, p99 539ms  (2.7x SLO)
* ``limit≈4500`` (two weeks of 5m) → expect further on-demand cost; Redis
  precompute (J4) is the mitigation for large windows.

J4 moves the compute from user-request time to closed-bar time: the WS
supervisor (one process per exchange) computes the full indicator
payload once per closed bar and writes it to Redis. The chart-indicators
handler then short-circuits on a Redis hit (≈24ms p95 for slice +
filter + serialize), serving every user from the pre-computed payload.

Pattern: this is the canonical "materialise on write, read on read"
shape used by TradingView, Coinglass, Cryptoquant. The supervisor side
pays the compute once per (symbol, timeframe, closed_bar); every chart
viewer reads the cheap path.

Why a separate SoT module
-------------------------
The Redis key shape, the precompute superset size, and the TTL policy
are referenced from FOUR different files (supervisor, handler, cache
keys, tests). Inlining a literal at any of those sites is the exact
"NO hardcoded values" violation the architect rules call out. The SoT
module is small (3 constants) but the references are many.
"""

from __future__ import annotations

from typing import Final

from src.shared.constants.calendar_monday_weekend_levels import MARKET_CHART_OHLCV_MAX_LIMIT

# Redis namespace prefix for the pre-computed chart-indicators payload.
# Sibling to ``ohlcv:`` (the supervisor's raw OHLCV tail) and
# ``ohlcv:fresh:`` (the supervisor's freshness heartbeat). Kept short
# because Redis key bytes are billed against the working set.
CHART_INDICATORS_PAYLOAD_KEY_PREFIX: Final[str] = "chart-indicators:"

# Number of OHLCV rows the supervisor's precompute pass operates on.
# The handler slices down to the user's requested ``limit``. Must be ≥
# ``MARKET_CHART_OHLCV_MAX_LIMIT`` so large full-chart windows stay on the
# Redis hit path (else fallback to on-demand calculate_all).
CHART_INDICATORS_PRECOMPUTE_SUPERSET_LIMIT: Final[int] = MARKET_CHART_OHLCV_MAX_LIMIT

# Cached payload TTL = TTL_BAR_MULTIPLIER x bar duration in seconds.
# 3x the bar period covers:
#   * brief supervisor outages (one missed write doesn't blank the cache),
#   * indicator-config deploys (stale payload self-expires within ~3 bars),
#   * timezone-edge cases where a "now" check thinks the bar hasn't closed.
# The handler ALSO does its own freshness check before serving; this TTL
# is the upper-bound safety net, not the primary freshness mechanism.
CHART_INDICATORS_TTL_BAR_MULTIPLIER: Final[int] = 3

# Tail-row threshold the supervisor checks BEFORE running calculate_all.
# Each indicator family has its own warmup window; FastFeatureCalculator
# rejects DataFrames shorter than ``config.max_warmup_periods`` with a
# ValueError. Per-tf warmups vary (slow EMAs need ~200 bars), but 100 is
# the floor below which no realistic config can succeed. Above it, the
# calculator's own warmup check applies; if it raises, the supervisor
# mixin's broad except catches it.
CHART_INDICATORS_PRECOMPUTE_MIN_TAIL_ROWS: Final[int] = 100

# Above this share of the requested window a "delta" stops being one, and the full payload is
# served instead (flagged `full`). Two reasons, both measured rather than aesthetic:
#
#   * VALUE. At 5m/4032 the full body is 623,778 B gzip and a 2-bar delta is 3,095 B. A delta
#     covering half the window saves under 2x, which does not pay for the client-side merge it
#     obliges.
#   * MEMORY. Delta entries are cached and their size is proportional to the bars they carry. An
#     unbounded slice lets a herd of long-stale clients fill the delta cache with near-full
#     payloads -- 256 x ~650 KB rather than 256 x ~30 KB. Bounding the SLICE bounds the cache,
#     which capping the entry COUNT alone cannot do.
CHART_INDICATORS_DELTA_MAX_WINDOW_FRACTION: Final[float] = 0.5

# Resident delta bodies per worker. Deliberately its own number AND its own cache instance:
# sharing the 128-entry response cache would sit one ~30 KB delta beside every ~2 MB full payload
# and halve the fulls that fit, which surfaces as evictions -- and the eviction counter is a
# documented decision gate (`chart_indicators_cache_metrics`: >5% ships J4). A delta is ~70x
# smaller, so a larger cap here costs ~8 MB and keeps that gate readable.
CHART_INDICATORS_DELTA_CACHE_MAX_ENTRIES: Final[int] = 256


__all__ = [
    "CHART_INDICATORS_DELTA_CACHE_MAX_ENTRIES",
    "CHART_INDICATORS_DELTA_MAX_WINDOW_FRACTION",
    "CHART_INDICATORS_PAYLOAD_KEY_PREFIX",
    "CHART_INDICATORS_PRECOMPUTE_MIN_TAIL_ROWS",
    "CHART_INDICATORS_PRECOMPUTE_SUPERSET_LIMIT",
    "CHART_INDICATORS_TTL_BAR_MULTIPLIER",
]
