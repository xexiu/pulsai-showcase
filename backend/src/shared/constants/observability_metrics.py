"""Constants for DB/Redis observability metrics.

KEEP LABEL CARDINALITY LOW. Adding labels per-table / per-key would explode
Prometheus series count. Only the operation/command identifier is labeled,
and values are restricted to the hard sets below — anything else is bucketed
under "OTHER".
"""

from __future__ import annotations

from collections.abc import Mapping

from src.shared.constants._env_resolvers import (
    env_source,
    resolve_positive_float,
)

# Private aliases so this module's own call sites are untouched by the consolidation.
_source = env_source
_resolve_positive_float = resolve_positive_float


OTHER_LABEL = "OTHER"

#: A request that runs more DB statements than this is logged as ``db_queries_per_request`` with its
#: route and count -- the in-process N+1 signal (prod has no pg_stat_statements). Measured 2026-10-05 on
#: localhost, the dashboard's 13 routes run 0-3 statements each and login 5; 4x that maximum leaves
#: normal requests far below while an N+1 (one statement per row) crosses it. Raise only with a measurement.
DB_QUERIES_PER_REQUEST_WARN: int = 20
"""Bucket label for operations/commands outside the curated known set."""

PROMETHEUS_METRICS_ROUTE = "/metrics"
"""Mount path for the Prometheus scrape endpoint (internal-only)."""

KNOWN_SQL_OPERATIONS: tuple[str, ...] = ("SELECT", "INSERT", "UPDATE", "DELETE")

#: The read verb, named so the write set can be DERIVED rather than retyped.
READ_SQL_OPERATION: str = "SELECT"

#: Every known operation that is not a read.
#:
#: DERIVED, because this set was written out literally in FIVE places — `_BATCHABLE_WRITES` and
#: `DbCompactThresholds.for_operation` in db_metrics.py, and three hand-typed tuples in its test
#: suite — one of them carrying a comment promising it "mirrors" another. A mirror maintained by
#: a comment drifts; the whole point of a constant is that adding a verb here changes every
#: answer at once, including what the tests check.
#:
#: It is the write set that matters twice over: these are the verbs a batch marker may relabel,
#: and the verbs judged on the write band. SELECT is excluded from both — a read issued inside a
#: bulk-write block is still a read, and must keep the tighter read band rather than inherit the
#: looser one.
WRITE_SQL_OPERATIONS: frozenset[str] = frozenset(KNOWN_SQL_OPERATIONS) - {READ_SQL_OPERATION}

KNOWN_REDIS_COMMANDS: tuple[str, ...] = (
    "GET",
    "SET",
    "DEL",
    # ADDED FROM A MEASUREMENT, not from reading the client. `redis OTHER` went CRITICAL on prod
    # 2026-09-06 and the bucket could not say what was in it; `other_commands_seen` reported
    # exactly one name, GETDEL — a command `RedisDataOps.getdel` has always issued and this list
    # never covered. Unlabelled, it shared a bucket with everything else unknown, so its latency
    # could neither be attributed nor excluded.
    "GETDEL",
    "EXPIRE",
    "TTL",
    "EXISTS",
    "INCR",
    # ADDED FROM A SECOND MEASUREMENT, 2026-09-06. Labelling GETDEL emptied the OTHER bucket for
    # ten minutes; the next page put `redis OTHER critical p95 0.4588 n=21` straight back, and
    # `other_commands_seen` named INCRBY. redis-py's `client.incr(key)` sends INCRBY key 1, so a
    # list containing INCR but not INCRBY misses every call the public rate limiter makes -- on
    # EVERY request. Two unlabelled commands found by the same field in one evening is the
    # argument for the field.
    "INCRBY",
    "DECR",
    "HGET",
    "HSET",
    "HGETALL",
    "HDEL",
    "LPUSH",
    "RPUSH",
    "LPOP",
    "RPOP",
    "LRANGE",
    "ZADD",
    "ZRANGE",
    "ZRANGEBYSCORE",
    "ZREM",
    "PING",
    "PUBLISH",
    "EVAL",
)

DB_DURATION_HISTOGRAM_BUCKETS_SECONDS: tuple[float, ...] = (
    0.0005,
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
)

REDIS_DURATION_HISTOGRAM_BUCKETS_SECONDS: tuple[float, ...] = (
    0.0001,
    0.0005,
    0.001,
    0.005,
    0.01,
    0.05,
    0.1,
    0.5,
    1.0,
)

OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES: tuple[tuple[str, int], ...] = (
    ("5m", 5),
    ("15m", 15),
    ("60m", 60),
)

# Default p95 thresholds for status badges. Tunable via DbCompactThresholds /
# RedisCompactThresholds. SELECT/Redis baselines assume same-region Postgres +
# Redis on Railway; tighten for prod after a week of real traffic.
# SELECT warn bumped 0.1 -> 0.3 (2026-06-18): a networked Timescale SELECT p95 of
# ~242ms is normal-busy and was producing warn-noise in the spike-health view.
# Critical (500ms) is unchanged; override per-environment via the *_ENV_VAR below.
DB_SELECT_P95_WARN_SECONDS = 0.3
DB_SELECT_P95_CRITICAL_SECONDS = 0.5
DB_WRITE_P95_WARN_SECONDS = 0.05
DB_WRITE_P95_CRITICAL_SECONDS = 0.2

# Label for an `executemany` write — a chunked bulk upsert, not a row.
#
# WHY IT IS NOT "INSERT". `OHLCVRepository.bulk_insert` upserts candles in chunks, and one such
# statement is a single sample whose duration scales with the CHUNK SIZE. Averaged into the
# single-row INSERT percentile it makes that percentile mean nothing, and against the write band
# above (50 ms warn / 200 ms critical, chosen for one row) it is a category error.
#
# MEASURED on prod 2026-09-06, db INSERT: p50 53-70 ms, p95 91-200 ms, p99 655 ms, with only
# 12-25 samples in a 5-minute window. A p95 over ~20 samples is barely more than the
# second-slowest one, so a single chunked upsert dragged it over 0.2 and paged the owner
# repeatedly — including at 09:02 and 12:34.
#
# The same class was already fixed once in this file: DB_SELECT_P95_WARN was bumped 0.1 -> 0.3
# in 2026-06 because a networked Timescale SELECT at ~242 ms is "normal-busy". Recalibrating the
# band was right there; here the band is fine and the BUCKET was wrong.
BULK_WRITE_LABEL = "BULK"
DB_OTHER_P95_WARN_SECONDS = 0.1
DB_OTHER_P95_CRITICAL_SECONDS = 0.5

# Networked-Railway calibration (2026-06-18): Redis is a managed add-on reached
# over the network, and the latency wrapper times wall-clock around the await
# (RTT + event-loop scheduling), so co-located bands (10ms/50ms) false-paged the
# spike watcher on a normal ~74ms p95. Defaults below assume networked Redis;
# co-located dev can tighten via the *_ENV_VAR overrides at the bottom of this file.
REDIS_OP_P95_WARN_SECONDS = 0.05
REDIS_OP_P95_CRITICAL_SECONDS = 0.15

# Per-endpoint latency tracking (Finding K).
# Curated allowlist — DO NOT add per-user / per-ID paths here. Prometheus
# label cardinality must stay bounded. Anything not in this set collapses
# to "OTHER" in the metric. Add a route here only when you want a dedicated
# admin-UI card row for it.
TRACKED_ENDPOINTS: tuple[str, ...] = (
    "/api/v1/market/chart-indicators",
    "/api/v1/market/ohlcv",
    "/admin/health",
    "/admin/health/observability",
    "/admin/health/workers",
    "/admin/health/summary",
    "/health",
    "/ready",
)
# Batch / CPU-heavy HTTP routes that regularly run for seconds-minutes.
# Excluded from endpoint spike-health percentiles so they do not poison the
# OTHER bucket (and falsely page CRITICAL) while a single uvicorn worker is
# legitimately busy. They still appear in access logs / OTEL if enabled.
# Bucket for the long-running routes below. They are kept OUT of the OTHER percentiles (a
# minutes-long backtest would page CRITICAL for everyone) but are still MEASURED here, under
# thresholds that suit them. Dropping the observation entirely was a blind spot: a backtest
# route degrading from 5 s to 300 s would have produced no signal anywhere.
LONG_RUNNING_LABEL: str = "LONG_RUNNING"

# Sync backtests are bounded — heavy ranges are rejected with a 400 pointing at
# /backtest/run-async — so a sync run past these is genuine degradation, not normal load.
ENDPOINT_LONG_RUNNING_P95_WARN_SECONDS: float = 30.0
ENDPOINT_LONG_RUNNING_P95_CRITICAL_SECONDS: float = 120.0

#: Marks a request as SYNTHETIC MONITORING rather than a user, so its latency stays out of the
#: percentiles that page a human.
#:
#: Measured on prod 2026-09-06: organic traffic on the chart routes is 1-2 requests per 5-minute
#: window, while the alert floor is DEFAULT_SPIKE_ALERT_MIN_SAMPLES = 20. So a recorded
#: `endpoint/OTHER` offender REQUIRES a burst that organic traffic cannot produce at that hour --
#: and the agent's 63-endpoint health sweep produces exactly that, supplying both the sample
#: volume that clears the floor and the cold-path latencies that set the percentile. Eight of
#: eight pages in 72h landed inside a window the sweep was running; the 18 consecutive hours with
#: no sweep recorded no degraded ticks at all.
#:
#: Deliberately an unmistakable token, never a generic one like "python" or "curl", which would
#: silently exclude real integrations. Any caller that sets it is asking not to be counted, which
#: is only ever correct for a prober that reads its own timings directly.
#:
#: SUPERSEDED IN SCOPE, 2026-09-06 evening. The "eight of eight pages in 72h" above was right and
#: too small: over 14 days `spike_health_events` holds 86 delivered pages, and asking of each
#: whether the same source+label was still critical two ticks later, 48 (56%) had ALREADY
#: RESOLVED. So the sweep was one burst source among several -- a dashboard load and a deploy's
#: cold cache do the same thing, and the watcher's own GETDEL/SET/INSERT did it too until
#: `_spike_watch_loop` began marking its ticks with this token.
#:
#: Excluding the prober was necessary and never sufficient: the deeper defect was that a p95 over
#: a 5-minute in-process window pages on ONE bad tick. That is fixed separately by
#: `DEFAULT_SPIKE_ALERT_CONSECUTIVE_CRITICAL_TICKS`, and this note is corrected here so the
#: 72-hour figure is not read later as the whole story.
SYNTHETIC_PROBE_USER_AGENT_TOKEN: str = "pulsai-synthetic-probe"

ENDPOINT_SPIKE_EXCLUDED_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/backtest",
    "/api/v1/backtest-hub",
    "/api/v1/admin/indicator-benchmark",
    "/api/v1/admin/training",
    "/api/v1/funding/backtest",
)
ENDPOINT_DURATION_HISTOGRAM_BUCKETS_SECONDS: tuple[float, ...] = (
    0.01,
    0.025,
    0.05,
    0.1,
    0.2,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)
# p95 thresholds — match `.cursorrules` / `CLAUDE.md` "API response < 200ms" SLO.
ENDPOINT_P95_WARN_SECONDS = 0.2
ENDPOINT_P95_CRITICAL_SECONDS = 1.0

# Warm-up grace period (Finding E in PLAN_db_performance_followups.md).
# Within this many seconds after process start, observations are dropped
# instead of recorded. This excludes connection-pool warm-up samples from
# polluting steady-state percentiles. Override per-process via
# PULSAI_OBSERVABILITY_WARMUP_GRACE_SECONDS env var (set to 0 in CI).
WARMUP_GRACE_SECONDS = 5.0

# Env var names — kept here as SoT so both the API (`src.main._init_observability`)
# and the Celery worker bootstrap (`src.workers.worker_prewarm.prewarm_worker_pool_child`)
# reference the same string.
#: How often the event-loop lag sampler asks the loop to wake it, in seconds.
#:
#: Short enough to catch a stall inside a single slow request, long enough that the sampler is
#: itself negligible: one timer every half second against a loop that services thousands.
EVENT_LOOP_LAG_SAMPLE_INTERVAL_SECONDS = 0.5

#: Samples retained. At the interval above this is a 2-minute rolling window -- long enough to
#: survive one bad request without being so long that a stall from ten minutes ago still shows.
EVENT_LOOP_LAG_WINDOW_SAMPLES = 240

#: How far back a stall stays available to EXPLAIN another source's percentile.
#:
#: A THIRD question, beside the two the bands above already separate. The window above is the
#: right length for "is the loop degraded NOW?" -- its own comment says so, and a stall should
#: stop colouring the loop's badge once it is over. But every other source slices its
#: observations into 5m/15m/60m, so a stall keeps inflating a dependency's 5-minute percentile
#: for three minutes after the loop has forgotten it.
#:
#: MEASURED on prod 2026-09-06, three consecutive ticks in `spike_health_events`: redis EXISTS
#: p95 0.0691687276586890 at both 23:29 and 23:30 -- byte-identical, so the same samples -- yet
#: `explained_by_loop_stall_seconds` was 0.354259068146348 at 23:29 and None at 23:30. Redis
#: answered in 69 ms throughout. The evidence had simply aged out of the only window the
#: evaluator could read, so the victim looked like a culprit again and paged.
#:
#: DERIVED from the dependency primary window rather than written down, because a retention that
#: must be "at least as long as theirs" is a mirror, and a mirror maintained by hand drifts the
#: first time someone retunes the other side.
EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS: float = float(OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES[0][1] * 60)

#: p95 lag bands. These measure the loop's OWN scheduling delay, not a request duration.
#:
#: A healthy asyncio loop wakes within a fraction of a millisecond of its timer. 50 ms of p95 lag
#: already means a quarter of the 200 ms API budget is gone before a handler does anything, so
#: that is the warn line. 250 ms means the budget cannot be met at all.
#:
#: For scale, the defect measured on 2026-09-03 held the loop for 9,241.9 ms -- about 37x this
#: critical threshold -- so the bands catch stalls far smaller than the one that prompted them.
EVENT_LOOP_LAG_P95_WARN_SECONDS = 0.05
EVENT_LOOP_LAG_P95_CRITICAL_SECONDS = 0.25

#: WORST-SAMPLE bands. p95 and max answer two different questions and both are needed.
#:
#: p95 asks "is the loop chronically late?". It cannot answer "did the loop stop?", because a
#: single block contributes ONE sample -- the sampler is asleep inside the freeze along with
#: everything else. One 9.24 s stall in a 240-sample window is 0.4% of the window, so p95
#: discards it and the badge reads `ok` during the very incident it exists to explain. Measured
#: 2026-09-05 against `spike_health_events`: 13 prod pages since 2026-08-14, and on 2026-08-26
#: five independent sources reported 6.150-6.627 s within 8% of each other -- one stall seen
#: through whatever happened to be awaiting, with nothing naming the loop.
#:
#: 1.0 s is critical because it equals ENDPOINT_P95_CRITICAL_SECONDS: a freeze that long has, on
#: its own, consumed the entire critical latency budget of every concurrent request before any
#: handler ran. 0.5 s is half of it. The band sits in a wide empty gap -- healthy samples are
#: sub-millisecond and every stall that actually paged prod was 2.1-9.2 s -- so ordinary
#: scheduling noise cannot trip it.
EVENT_LOOP_LAG_MAX_WARN_SECONDS = 0.5
EVENT_LOOP_LAG_MAX_CRITICAL_SECONDS = 1.0

#: Single label for the loop in the shared compact-view contract. DB labels by SQL operation and
#: Redis by command because those have many; a process has exactly one event loop.
EVENT_LOOP_LAG_LABEL = "LAG"

#: Source key for the loop in the spike-health compact views, beside `db` / `redis` / `endpoint`.
EVENT_LOOP_SOURCE = "event_loop"

SLOW_QUERY_THRESHOLD_ENV_VAR = "PULSAI_DB_SLOW_QUERY_THRESHOLD_SECONDS"
WARMUP_GRACE_ENV_VAR = "PULSAI_OBSERVABILITY_WARMUP_GRACE_SECONDS"

# Redis compact-view p95 threshold overrides (SoT). Co-located dev (sub-ms) and
# networked prod (tens of ms) want different bands; these let ops tune
# per-environment with no redeploy. Resolver convention mirrors spike_alert /
# ohlcv_sources / signal_freshness: strictly-positive float, falling back to the
# default on missing / invalid / non-positive input.
REDIS_OP_P95_WARN_ENV_VAR = "PULSAI_REDIS_OP_P95_WARN_SECONDS"
REDIS_OP_P95_CRITICAL_ENV_VAR = "PULSAI_REDIS_OP_P95_CRITICAL_SECONDS"


def resolve_redis_op_p95_warn_seconds(env: Mapping[str, str] | None = None) -> float:
    """Resolve the Redis op p95 *warn* threshold (seconds); missing/invalid → default."""
    return _resolve_positive_float(
        env=env,
        var=REDIS_OP_P95_WARN_ENV_VAR,
        default=REDIS_OP_P95_WARN_SECONDS,
    )


def resolve_redis_op_p95_critical_seconds(env: Mapping[str, str] | None = None) -> float:
    """Resolve the Redis op p95 *critical* threshold (seconds); missing/invalid → default."""
    return _resolve_positive_float(
        env=env,
        var=REDIS_OP_P95_CRITICAL_ENV_VAR,
        default=REDIS_OP_P95_CRITICAL_SECONDS,
    )


# DB SELECT compact-view p95 threshold overrides (SoT). Networked Timescale SELECT
# latency varies by deployment (a ~242ms p95 was normal-busy warn-noise in the
# 2026-06-18 spike-health view); these let ops tune per-environment with no redeploy.
DB_SELECT_P95_WARN_ENV_VAR = "PULSAI_DB_SELECT_P95_WARN_SECONDS"
DB_SELECT_P95_CRITICAL_ENV_VAR = "PULSAI_DB_SELECT_P95_CRITICAL_SECONDS"


def resolve_db_select_p95_warn_seconds(env: Mapping[str, str] | None = None) -> float:
    """Resolve the DB SELECT p95 *warn* threshold (seconds); missing/invalid → default."""
    return _resolve_positive_float(
        env=env,
        var=DB_SELECT_P95_WARN_ENV_VAR,
        default=DB_SELECT_P95_WARN_SECONDS,
    )


def resolve_db_select_p95_critical_seconds(env: Mapping[str, str] | None = None) -> float:
    """Resolve the DB SELECT p95 *critical* threshold (seconds); missing/invalid → default."""
    return _resolve_positive_float(
        env=env,
        var=DB_SELECT_P95_CRITICAL_ENV_VAR,
        default=DB_SELECT_P95_CRITICAL_SECONDS,
    )
