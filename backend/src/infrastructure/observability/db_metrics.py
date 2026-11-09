"""Prometheus DB query duration histogram + compact percentile view.

Mirrors the time-windowed pattern from `live_signal_metrics.py`. Histogram is
created lazily so production code never crashes when `prometheus_client` is
unavailable (e.g. in stripped-down test envs).

SECURITY / COST: only the operation kind (SELECT/INSERT/UPDATE/DELETE/OTHER)
is recorded as a label — DO NOT add table or SQL text labels here. Doing so
would explode Prometheus series cardinality.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import timedelta
from time import perf_counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

from src.infrastructure.observability._compact_view_helpers import (
    compute_percentiles,
    compute_threshold_status,
    trim_old_observations,
)
from src.infrastructure.observability.bulk_write_context import (
    bulk_write_rows,
    is_bulk_write_in_progress,
)
from src.infrastructure.observability.request_query_count import note_db_query_for_request
from src.infrastructure.observability.synthetic_probe_context import (
    is_current_request_synthetic,
)
from src.shared.constants.observability_metrics import (
    BULK_WRITE_LABEL,
    DB_DURATION_HISTOGRAM_BUCKETS_SECONDS,
    DB_OTHER_P95_CRITICAL_SECONDS,
    DB_OTHER_P95_WARN_SECONDS,
    DB_WRITE_P95_CRITICAL_SECONDS,
    DB_WRITE_P95_WARN_SECONDS,
    KNOWN_SQL_OPERATIONS,
    OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES,
    OTHER_LABEL,
    READ_SQL_OPERATION,
    SLOW_QUERY_THRESHOLD_ENV_VAR,
    WARMUP_GRACE_ENV_VAR,
    WARMUP_GRACE_SECONDS,
    WRITE_SQL_OPERATIONS,
    resolve_db_select_p95_critical_seconds,
    resolve_db_select_p95_warn_seconds,
)
from src.shared.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)

_PROCESS_START_PERF = perf_counter()


def _seconds_since_process_start() -> float:
    """Wall-clock proxy used by the warm-up gate. Patchable in tests."""
    return perf_counter() - _PROCESS_START_PERF


def _warmup_grace_seconds() -> float:
    """Effective warm-up grace; honors `WARMUP_GRACE_ENV_VAR`."""
    import os

    raw = os.environ.get(WARMUP_GRACE_ENV_VAR, "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return WARMUP_GRACE_SECONDS


def _resolve_slow_query_threshold_from_env() -> float | None:
    """Read SLOW_QUERY_THRESHOLD_ENV_VAR; None when unset / non-positive / malformed.

    Shared by `src.main._init_observability` (API) and
    `src.workers.worker_prewarm.prewarm_worker_pool_child` (Celery) so the
    same env var works identically in both processes — single source of
    truth, no duplication.
    """
    import os

    raw = os.environ.get(SLOW_QUERY_THRESHOLD_ENV_VAR, "").strip()
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        logger.warning("%s=%r is not a number; the slow-query log stays off", SLOW_QUERY_THRESHOLD_ENV_VAR, raw)
        return None
    if parsed <= 0:
        logger.warning("%s=%r is not positive; the slow-query log stays off", SLOW_QUERY_THRESHOLD_ENV_VAR, raw)
        return None
    return parsed


_PREFIX_LEN = 7  # max length of any value in KNOWN_SQL_OPERATIONS + 1

_SLOW_QUERY_SQL_MAX_LEN = 500  # truncate SQL in slow-query logs (no params logged)


@dataclass(frozen=True)
class DbCompactThresholds:
    """Per-operation p95 thresholds for status badges in the compact view."""

    select_p95_warn_seconds: float = field(default_factory=resolve_db_select_p95_warn_seconds)
    select_p95_critical_seconds: float = field(default_factory=resolve_db_select_p95_critical_seconds)
    write_p95_warn_seconds: float = DB_WRITE_P95_WARN_SECONDS
    write_p95_critical_seconds: float = DB_WRITE_P95_CRITICAL_SECONDS
    other_p95_warn_seconds: float = DB_OTHER_P95_WARN_SECONDS
    other_p95_critical_seconds: float = DB_OTHER_P95_CRITICAL_SECONDS

    def for_operation(self, operation: str) -> tuple[float, float]:
        """Return (warn, critical) p95 thresholds for the given operation.

        BULK shares the WRITE band, and that is a derivation rather than a choice. Its samples are
        normalised PER ROW (see `install_db_event_listeners`), so a batched row and an unbatched
        row are finally the same unit — and the entire claim batching makes is that a row costs
        LESS inside a batch. Judging both against one band states that claim as a check: if a
        batched row costs what a single-row INSERT costs, the batching bought nothing and the
        alert is earned.

        The first version parked BULK on the OTHER band instead, because the raw per-statement
        duration had no defensible threshold at all. That was true while the number was
        uninterpretable; normalising removed the reason.
        """
        if operation == READ_SQL_OPERATION:
            return self.select_p95_warn_seconds, self.select_p95_critical_seconds
        if operation in {*WRITE_SQL_OPERATIONS, BULK_WRITE_LABEL}:
            return self.write_p95_warn_seconds, self.write_p95_critical_seconds
        return self.other_p95_warn_seconds, self.other_p95_critical_seconds


_db_lock = threading.Lock()
_db_query_duration_histogram: Any = None


@dataclass
class _TimedDbValue:
    at: Any
    operation: str
    value: float


@dataclass
class _DbWindowState:
    observations: list[_TimedDbValue] = field(default_factory=list)


_db_window_state = _DbWindowState()


def _trim_old(now: Any) -> None:
    _db_window_state.observations = trim_old_observations(_db_window_state.observations, now)


def _classify_sql_operation(statement: str, *, executemany: bool = False) -> str:
    """Map a SQL string to a low-cardinality operation label.

    An `executemany` statement is labelled BULK regardless of its verb, because what makes it a
    different thing to measure is the batching, not whether it inserts or updates. Splitting it
    per verb would add label cardinality without adding insight.

    Defaults to False so every existing caller — and every test — keeps its current meaning.
    """
    operation = OTHER_LABEL
    if statement:
        prefix = statement.lstrip()[:_PREFIX_LEN].upper()
        for op in KNOWN_SQL_OPERATIONS:
            if prefix.startswith(op):
                operation = op
                break

    # Either signal marks a batch, and the SECOND is the load-bearing half.
    #
    # `executemany` covers a driver-level batch. It does NOT cover the case this label was
    # written for: `pg_insert(...).values(chunk)` renders ONE multi-row VALUES statement, so
    # SQLAlchemy reports executemany=False for a write carrying thousands of rows. The caller
    # declares that one, because only the caller can know it.
    #
    # Applied to WRITES only. The declaration means "the writes in this block are batched", not
    # "relabel everything in here" — a SELECT issued inside the block is still an ordinary read
    # and must keep the read band. The first draft returned BULK before looking at the verb, and
    # the test written for it had a name that contradicted its own assertion.
    if operation in WRITE_SQL_OPERATIONS and (executemany or is_bulk_write_in_progress()):
        return BULK_WRITE_LABEL
    return operation


#: How many DB observations were dropped for belonging to a synthetic probe request.
#:
#: Published in the compact view so the exclusion is VISIBLE. An invisible exclusion makes
#: "only a prober is running" and "healthy and idle" render identically, which is how a real
#: regression hides behind a filter nobody can see (ARCHITECTURE_PATTERNS section 5).
_synthetic_db_samples_dropped: int = 0


def _note_synthetic_db_sample_dropped() -> None:
    """Count one dropped probe-caused observation."""
    global _synthetic_db_samples_dropped
    with _db_lock:
        _synthetic_db_samples_dropped += 1


def synthetic_db_samples_dropped() -> int:
    """How many DB observations were excluded as synthetic since process start."""
    with _db_lock:
        return _synthetic_db_samples_dropped


def reset_synthetic_db_samples_dropped_for_tests() -> None:
    """Zero the drop counter (unit tests only)."""
    global _synthetic_db_samples_dropped
    with _db_lock:
        _synthetic_db_samples_dropped = 0


def observe_db_query_duration_seconds(operation: str, duration_seconds: float) -> None:
    """Record one query into the windowed deque and Prometheus histogram.

    During the warm-up grace window (first `WARMUP_GRACE_SECONDS` after
    process start), observations are dropped — connection pools are warming
    and the samples would skew p50/p95/p99 (Finding E).

    Work caused by a SYNTHETIC PROBE is dropped for the same reason: it is not user traffic and
    it must not page. The endpoint view learned this on 2026-09-06 and this one did not, so the
    agent's own authenticated measurements kept paging the owner with `db INSERT critical` —
    the endpoint was clean and the INSERTs underneath it were not. Counted, not silently
    dropped, so "only a prober is running" never renders as "healthy and idle".
    """
    if _seconds_since_process_start() < _warmup_grace_seconds():
        return
    if is_current_request_synthetic():
        _note_synthetic_db_sample_dropped()
        return
    if duration_seconds < 0:
        duration_seconds = 0.0

    if operation == BULK_WRITE_LABEL:
        # PER ROW, so the number means something. A chunked upsert's duration scales with its
        # chunk size: 216 ms is excellent for 4,000 rows and terrible for 3, and the raw figure
        # cannot tell those apart. Dividing makes a batched row directly comparable with an
        # unbatched one, which is the claim batching makes and the reason BULK can share the
        # write band at all.
        #
        # HERE and not in the event listener, though the listener is the only caller today. This
        # function is where a duration BECOMES a sample - the warm-up drop and the synthetic drop
        # both live here for the same reason. Normalising upstream would mean any future caller
        # silently records an un-normalised BULK sample into the same window, mixing two units
        # under one label, which is the bug this whole change exists to remove.
        #
        # `bulk_write_rows()` is > 0 only when a caller DECLARED the count. The `or 1` covers
        # SQLAlchemy's own executemany path, where nobody declared one: that sample stays raw
        # rather than being scaled by an invented divisor.
        duration_seconds = duration_seconds / (bulk_write_rows() or 1)

    with _db_lock:
        now = utc_now()
        _db_window_state.observations.append(_TimedDbValue(at=now, operation=operation, value=duration_seconds))
        _trim_old(now)

    global _db_query_duration_histogram
    try:
        from prometheus_client import Histogram
    except ImportError:
        return

    with _db_lock:
        if _db_query_duration_histogram is None:
            _db_query_duration_histogram = Histogram(
                "pulsai_db_query_duration_seconds",
                "SQLAlchemy query duration grouped by operation kind.",
                labelnames=("operation",),
                buckets=DB_DURATION_HISTOGRAM_BUCKETS_SECONDS,
            )
    _db_query_duration_histogram.labels(operation=operation).observe(duration_seconds)


_LISTENER_SENTINEL_ATTR = "_pulsai_db_metrics_installed"
_QUERY_START_KEY = "_pulsai_query_start"


def install_db_event_listeners(
    sync_engine: Engine,
    *,
    slow_query_threshold_seconds: float | None = None,
) -> None:
    """Attach `before/after_cursor_execute` listeners (idempotent per-engine).

    When `slow_query_threshold_seconds` is provided, queries exceeding the
    threshold also emit a WARNING log entry with the (truncated) SQL on
    `extra={"sql": ...}` — SREs can copy-paste it into `EXPLAIN ANALYZE`.
    Bind parameters are NOT logged for security/PII reasons.
    """
    if getattr(sync_engine, _LISTENER_SENTINEL_ATTR, False):
        return

    from sqlalchemy import event

    def _before(conn: Any, _cursor: Any, _statement: str, *_a: Any, **_kw: Any) -> None:
        conn.info[_QUERY_START_KEY] = perf_counter()

    def _after(
        conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any = None,
        _context: Any = None,
        executemany: bool = False,
        **_kw: Any,
    ) -> None:
        # `executemany` was always here — SQLAlchemy passes it as the sixth positional argument —
        # and was being swallowed by `*_a`. Naming it is the whole fix: it is the difference
        # between one row and a chunked upsert of thousands, which have no business sharing a
        # percentile or a threshold.
        note_db_query_for_request()
        start = conn.info.pop(_QUERY_START_KEY, None)
        if start is None:
            return
        elapsed = perf_counter() - start
        operation = _classify_sql_operation(statement, executemany=bool(executemany))
        observe_db_query_duration_seconds(operation, elapsed)
        if slow_query_threshold_seconds is not None and elapsed >= slow_query_threshold_seconds:
            logger.warning(
                "slow_db_query",
                extra={
                    "operation": operation,
                    "duration_seconds": elapsed,
                    "sql": (statement or "")[:_SLOW_QUERY_SQL_MAX_LEN],
                },
            )

    event.listen(sync_engine, "before_cursor_execute", _before)
    event.listen(sync_engine, "after_cursor_execute", _after)
    setattr(sync_engine, _LISTENER_SENTINEL_ATTR, True)


def get_db_compact_health_view(
    *,
    now: Any | None = None,
    metric_windows: tuple[tuple[str, int], ...] | None = None,
    thresholds: DbCompactThresholds | None = None,
) -> dict[str, Any]:
    """Return compact percentile view: windows x operations -> {count, p50, p95, p99, status}."""
    window_minutes: dict[str, int] = dict(metric_windows or OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES)
    now_dt = utc_now() if now is None else now
    th = thresholds or DbCompactThresholds()

    with _db_lock:
        _trim_old(now_dt)
        snapshot = list(_db_window_state.observations)

    # BULK is enumerated here or it never appears in the view at all — the loop below only
    # reports labels it is asked about, so an unlisted label is collected and then silently
    # dropped. That is how a metric ends up measured and invisible.
    ops = (*KNOWN_SQL_OPERATIONS, BULK_WRITE_LABEL, OTHER_LABEL)
    by_label: dict[str, dict[str, dict[str, Any]]] = {}
    for window_key, minutes in window_minutes.items():
        floor = now_dt - timedelta(minutes=minutes)
        by_op: dict[str, dict[str, Any]] = {}
        for op in ops:
            values = [o.value for o in snapshot if o.at >= floor and o.operation == op]
            percentiles = compute_percentiles(values)
            warn, critical = th.for_operation(op)
            by_op[op] = {
                "count": len(values),
                **percentiles,
                "status": compute_threshold_status(percentiles["p95"], warn=warn, critical=critical),
            }
        by_label[window_key] = by_op

    primary_window_key = next(iter(window_minutes.keys()))
    return {
        "windows": list(window_minutes.keys()),
        "primary_window": primary_window_key,
        "by_label": by_label,
        # THE EXCLUSION MUST BE VISIBLE. Counting the drops and never publishing them is the
        # inert-value defect this repo has shipped twice (`spot_bh_final`,
        # `combo_top_raw_incl_ruin`) -- and I shipped it a third time in the commit that added
        # the counter, whose message claimed this field already existed. Without it, "a prober
        # was the only traffic" and "healthy and idle" are the same empty window.
        "synthetic_samples_dropped": synthetic_db_samples_dropped(),
    }


__all__ = [
    "get_db_compact_health_view",
    "install_db_event_listeners",
    "observe_db_query_duration_seconds",
    "reset_synthetic_db_samples_dropped_for_tests",
    "synthetic_db_samples_dropped",
]
