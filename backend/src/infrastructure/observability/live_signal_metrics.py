"""Prometheus metrics for live-signal Celery tasks (Phase 3 observability).

Histogram is created lazily so importing this module never fails tests that
patch prometheus or omit the dependency (production installs include it).

@see docs/06-devops/PERFORMANCE_MONITORING.md §2
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import timedelta
from statistics import quantiles
from typing import Any

from src.infrastructure.observability._compact_view_helpers import compute_threshold_status
from src.shared.constants.live_signal_observability import LIVE_SIGNAL_COMPACT_METRIC_WINDOWS_MINUTES
from src.shared.constants.spike_alert import (
    COMPACT_STATUS_CRITICAL,
    COMPACT_STATUS_OK,
    COMPACT_STATUS_UNKNOWN,
    COMPACT_STATUS_WARN,
)
from src.shared.utils.datetime_utils import utc_now

_hist_lock = threading.Lock()
_live_signal_task_duration_histogram: Any = None
_live_signal_queue_wait_histogram: Any = None
_live_signal_persist_commit_histogram: Any = None
_live_signal_ohlcv_tier_counter: Any = None


@dataclass
class _TimedValue:
    at: Any
    value: float
    timeframe: str | None = None


@dataclass
class _TimedTier:
    at: Any
    tier: str
    timeframe: str | None = None


@dataclass
class _MetricsWindowState:
    queue_wait_observations: list[_TimedValue] = field(default_factory=list)
    persist_commit_observations: list[_TimedValue] = field(default_factory=list)
    persist_commit_errors: list[Any] = field(default_factory=list)
    ohlcv_tier_events: list[_TimedTier] = field(default_factory=list)


_metrics_window_state = _MetricsWindowState()


@dataclass(frozen=True)
class LiveSignalCompactThresholds:
    queue_wait_warn_seconds: float
    queue_wait_critical_seconds: float
    persist_commit_warn_seconds: float
    persist_commit_critical_seconds: float
    persist_error_rate_warn: float
    persist_error_rate_critical: float
    exchange_tier_ratio_warn: float = 0.2
    exchange_tier_ratio_critical: float = 0.4


def _trim_old(now: Any) -> None:
    _trim_old_state(_metrics_window_state, now)


def _trim_old_state(state: _MetricsWindowState, now: Any) -> None:
    floor = now - timedelta(hours=1)
    state.queue_wait_observations = [x for x in state.queue_wait_observations if x.at >= floor]
    state.persist_commit_observations = [x for x in state.persist_commit_observations if x.at >= floor]
    state.persist_commit_errors = [x for x in state.persist_commit_errors if x.at >= floor]
    state.ohlcv_tier_events = [x for x in state.ohlcv_tier_events if x.at >= floor]


def _resolve_observation_state() -> _MetricsWindowState:
    """Merge worker Redis samples with this process buffer (admin health reads both)."""
    from src.infrastructure.observability.live_signal_observability_redis import (
        load_metrics_window_state_from_redis_sync,
        merge_metrics_window_states,
    )

    with _hist_lock:
        local = _MetricsWindowState(
            queue_wait_observations=list(_metrics_window_state.queue_wait_observations),
            persist_commit_observations=list(_metrics_window_state.persist_commit_observations),
            persist_commit_errors=list(_metrics_window_state.persist_commit_errors),
            ohlcv_tier_events=list(_metrics_window_state.ohlcv_tier_events),
        )
    return merge_metrics_window_states(load_metrics_window_state_from_redis_sync(), local)


def _error_rate(errors: int, sample_count: int) -> float | None:
    if sample_count == 0:
        return None
    return errors / sample_count


def _worst_compact_status(*statuses: str) -> str:
    if COMPACT_STATUS_CRITICAL in statuses:
        return COMPACT_STATUS_CRITICAL
    if COMPACT_STATUS_WARN in statuses:
        return COMPACT_STATUS_WARN
    if all(s == COMPACT_STATUS_UNKNOWN for s in statuses):
        return COMPACT_STATUS_UNKNOWN
    return COMPACT_STATUS_OK


def _window_values(
    values: list[_TimedValue],
    now: Any,
    *,
    minutes: int,
    timeframe: str | None = None,
) -> list[float]:
    floor = now - timedelta(minutes=minutes)
    return [v.value for v in values if v.at >= floor and (timeframe is None or v.timeframe == timeframe)]


def _window_errors(values: list[_TimedValue], now: Any, *, minutes: int, timeframe: str | None = None) -> int:
    floor = now - timedelta(minutes=minutes)
    return sum(1 for v in values if v.at >= floor and (timeframe is None or v.timeframe == timeframe))


def _percentiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None, "p99": None}
    if len(values) == 1:
        base = values[0]
        return {"p50": base, "p95": base, "p99": base}
    p50, p95, p99 = (
        quantiles(values, n=100, method="inclusive")[49],
        quantiles(values, n=100, method="inclusive")[94],
        quantiles(values, n=100, method="inclusive")[98],
    )
    return {"p50": p50, "p95": p95, "p99": p99}


def observe_live_signal_task_duration_seconds(duration_seconds: float) -> None:
    """Record wall-clock duration of ``generate_live_signals`` (one Celery run)."""
    if duration_seconds < 0:
        duration_seconds = 0.0
    try:
        from prometheus_client import Histogram
    except ImportError:
        return

    global _live_signal_task_duration_histogram

    with _hist_lock:
        if _live_signal_task_duration_histogram is None:
            _live_signal_task_duration_histogram = Histogram(
                "pulsai_live_signal_task_duration_seconds",
                "Wall-clock duration of the generate_live_signals Celery task (alignment through persist, notify, and confluence).",
                buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
            )
    _live_signal_task_duration_histogram.observe(duration_seconds)


def observe_live_signal_queue_wait_seconds(queue_wait_seconds: float, timeframe: str | None = None) -> None:
    """Record queue wait from scheduled ETA to task start when available."""
    if queue_wait_seconds < 0:
        queue_wait_seconds = 0.0
    with _hist_lock:
        now = utc_now()
        _metrics_window_state.queue_wait_observations.append(_TimedValue(at=now, value=queue_wait_seconds, timeframe=timeframe))
        _trim_old(now)
    from src.infrastructure.observability.live_signal_observability_redis import append_queue_wait_sample_sync

    append_queue_wait_sample_sync(queue_wait_seconds, timeframe=timeframe)
    try:
        from prometheus_client import Histogram
    except ImportError:
        return

    global _live_signal_queue_wait_histogram
    with _hist_lock:
        if _live_signal_queue_wait_histogram is None:
            _live_signal_queue_wait_histogram = Histogram(
                "pulsai_live_signal_queue_wait_seconds",
                "Delay between task ETA and worker start for generate_live_signals.",
                buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
            )
    _live_signal_queue_wait_histogram.observe(queue_wait_seconds)


def observe_live_signal_ohlcv_tier_choice(tier: str, timeframe: str | None = None) -> None:
    """Count which OHLCV tier served live-signal reads."""
    with _hist_lock:
        now = utc_now()
        _metrics_window_state.ohlcv_tier_events.append(_TimedTier(at=now, tier=tier, timeframe=timeframe))
        _trim_old(now)
    from src.infrastructure.observability.live_signal_observability_redis import append_ohlcv_tier_sample_sync

    append_ohlcv_tier_sample_sync(tier, timeframe=timeframe)
    try:
        from prometheus_client import Counter
    except ImportError:
        return

    global _live_signal_ohlcv_tier_counter
    with _hist_lock:
        if _live_signal_ohlcv_tier_counter is None:
            _live_signal_ohlcv_tier_counter = Counter(
                "pulsai_live_signal_ohlcv_tier_total",
                "OHLCV read tier used for live signal generation.",
                labelnames=("tier",),
            )
    _live_signal_ohlcv_tier_counter.labels(tier=tier).inc()


def observe_live_signal_persist_commit_duration_seconds(
    duration_seconds: float,
    timeframe: str | None = None,
) -> None:
    """Record DB persist+commit duration for one generated signal."""
    if duration_seconds < 0:
        duration_seconds = 0.0
    with _hist_lock:
        now = utc_now()
        _metrics_window_state.persist_commit_observations.append(_TimedValue(at=now, value=duration_seconds, timeframe=timeframe))
        _trim_old(now)
    from src.infrastructure.observability.live_signal_observability_redis import append_persist_commit_sample_sync

    append_persist_commit_sample_sync(duration_seconds, timeframe=timeframe)
    try:
        from prometheus_client import Histogram
    except ImportError:
        return

    global _live_signal_persist_commit_histogram
    with _hist_lock:
        if _live_signal_persist_commit_histogram is None:
            _live_signal_persist_commit_histogram = Histogram(
                "pulsai_live_signal_persist_commit_duration_seconds",
                "Duration of signal repository save plus DB commit in live generation.",
                buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
            )
    _live_signal_persist_commit_histogram.observe(duration_seconds)


def observe_live_signal_persist_commit_error(timeframe: str | None = None) -> None:
    """Record a persist/commit error occurrence for compact health view."""
    with _hist_lock:
        now = utc_now()
        _metrics_window_state.persist_commit_errors.append(_TimedValue(at=now, value=1.0, timeframe=timeframe))
        _trim_old(now)
    from src.infrastructure.observability.live_signal_observability_redis import append_persist_error_sample_sync

    append_persist_error_sample_sync(timeframe=timeframe)


def get_live_signal_compact_health_view(
    *,
    now: Any | None = None,
    thresholds: LiveSignalCompactThresholds,
    production_timeframes: list[str] | None = None,
    metric_windows: tuple[tuple[str, int], ...] | None = None,
) -> dict[str, Any]:
    """Return compact observability view for admin/health."""
    window_minutes: dict[str, int] = dict(metric_windows or LIVE_SIGNAL_COMPACT_METRIC_WINDOWS_MINUTES)
    now_dt = utc_now() if now is None else now
    state = _resolve_observation_state()
    _trim_old_state(state, now_dt)

    queue_values = {key: _window_values(state.queue_wait_observations, now_dt, minutes=minutes) for key, minutes in window_minutes.items()}
    persist_values = {key: _window_values(state.persist_commit_observations, now_dt, minutes=minutes) for key, minutes in window_minutes.items()}
    persist_errors = {key: _window_errors(state.persist_commit_errors, now_dt, minutes=minutes) for key, minutes in window_minutes.items()}

    def _tier_window(minutes: int, *, timeframe: str | None = None) -> dict[str, Any]:
        floor = now_dt - timedelta(minutes=minutes)
        events = [x.tier for x in state.ohlcv_tier_events if x.at >= floor and (timeframe is None or x.timeframe == timeframe)]
        total = len(events)
        counts: dict[str, int] = {}
        for tier in events:
            counts[tier] = counts.get(tier, 0) + 1
        if total == 0:
            return {
                "total": 0,
                "counts_by_tier": {},
                "ratios_by_tier": {},
                "redis_namespaced_ratio": None,
                "exchange_namespaced_ratio": None,
            }
        ratios_by_tier = {k: v / total for k, v in counts.items()}
        return {
            "total": total,
            "counts_by_tier": counts,
            "ratios_by_tier": ratios_by_tier,
            "redis_namespaced_ratio": ratios_by_tier.get("redis_namespaced"),
            "exchange_namespaced_ratio": ratios_by_tier.get("exchange_namespaced"),
        }

    queue_windows = {key: {"count": len(values), **_percentiles(values)} for key, values in queue_values.items()}
    persist_windows = {
        key: {
            "count": len(values),
            **_percentiles(values),
            "errors": persist_errors[key],
            "error_rate": _error_rate(persist_errors[key], len(values)),
        }
        for key, values in persist_values.items()
    }
    tier_windows = {key: _tier_window(minutes) for key, minutes in window_minutes.items()}
    primary_window_key = next(iter(window_minutes.keys()))

    queue_status = compute_threshold_status(
        queue_windows[primary_window_key]["p99"],
        warn=thresholds.queue_wait_warn_seconds,
        critical=thresholds.queue_wait_critical_seconds,
    )
    persist_status_p95 = compute_threshold_status(
        persist_windows[primary_window_key]["p95"],
        warn=thresholds.persist_commit_warn_seconds,
        critical=thresholds.persist_commit_critical_seconds,
    )
    persist_status_err = compute_threshold_status(
        persist_windows[primary_window_key]["error_rate"],
        warn=thresholds.persist_error_rate_warn,
        critical=thresholds.persist_error_rate_critical,
    )
    persist_status = _worst_compact_status(persist_status_p95, persist_status_err)
    tier_status = compute_threshold_status(
        tier_windows[primary_window_key]["exchange_namespaced_ratio"],
        warn=thresholds.exchange_tier_ratio_warn,
        critical=thresholds.exchange_tier_ratio_critical,
    )
    observed_timeframes = {x.timeframe for x in state.ohlcv_tier_events if x.timeframe} | {
        x.timeframe for x in state.persist_commit_observations if x.timeframe
    }
    requested_timeframes = set(production_timeframes or [])
    all_timeframes = sorted(observed_timeframes | requested_timeframes)
    persist_by_timeframe = {
        window_key: {
            timeframe: {
                "count": len(
                    p_tf := _window_values(
                        state.persist_commit_observations,
                        now_dt,
                        minutes=window_minutes[window_key],
                        timeframe=timeframe,
                    )
                ),
                **_percentiles(p_tf),
                "errors": _window_errors(
                    state.persist_commit_errors,
                    now_dt,
                    minutes=window_minutes[window_key],
                    timeframe=timeframe,
                ),
                "error_rate": _error_rate(
                    _window_errors(
                        state.persist_commit_errors,
                        now_dt,
                        minutes=window_minutes[window_key],
                        timeframe=timeframe,
                    ),
                    len(p_tf),
                ),
            }
            for timeframe in all_timeframes
        }
        for window_key in window_minutes
    }
    ohlcv_by_timeframe = {
        window_key: {timeframe: _tier_window(window_minutes[window_key], timeframe=timeframe) for timeframe in all_timeframes}
        for window_key in window_minutes
    }

    return {
        "windows": list(window_minutes.keys()),
        "primary_window": primary_window_key,
        "queue_wait": {
            "windows": queue_windows,
            "status": queue_status,
        },
        "ohlcv_tier_ratio": {
            "windows": tier_windows,
            "status": tier_status,
            "by_timeframe": ohlcv_by_timeframe,
        },
        "persist_commit": {
            "windows": persist_windows,
            "status": persist_status,
            "by_timeframe": persist_by_timeframe,
        },
    }


__all__ = [
    "LiveSignalCompactThresholds",
    "get_live_signal_compact_health_view",
    "observe_live_signal_ohlcv_tier_choice",
    "observe_live_signal_persist_commit_duration_seconds",
    "observe_live_signal_persist_commit_error",
    "observe_live_signal_queue_wait_seconds",
    "observe_live_signal_task_duration_seconds",
]
