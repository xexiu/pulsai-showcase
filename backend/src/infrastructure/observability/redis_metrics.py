"""Prometheus Redis op duration histogram + compact percentile view.

Mirrors the time-windowed pattern from `live_signal_metrics.py` and the
companion `db_metrics.py`. Histogram is created lazily so production code
never crashes when `prometheus_client` is unavailable.

SECURITY / COST: only the command name (GET/SET/HGET/.../OTHER) is recorded
as a label — DO NOT add key labels here. Doing so would explode Prometheus
series cardinality.
"""

from __future__ import annotations

import functools
import threading
from dataclasses import dataclass, field
from datetime import timedelta
from time import perf_counter
from typing import Any

from src.infrastructure.observability._compact_view_helpers import (
    compute_percentiles,
    compute_threshold_status,
    trim_old_observations,
)
from src.infrastructure.observability.synthetic_probe_context import (
    is_current_request_synthetic,
)
from src.shared.constants.observability_metrics import (
    KNOWN_REDIS_COMMANDS,
    OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES,
    OTHER_LABEL,
    REDIS_DURATION_HISTOGRAM_BUCKETS_SECONDS,
    WARMUP_GRACE_SECONDS,
    resolve_redis_op_p95_critical_seconds,
    resolve_redis_op_p95_warn_seconds,
)
from src.shared.utils.datetime_utils import utc_now

_PROCESS_START_PERF = perf_counter()


def _seconds_since_process_start() -> float:
    """Wall-clock proxy used by the warm-up gate. Patchable in tests."""
    return perf_counter() - _PROCESS_START_PERF


def _warmup_grace_seconds() -> float:
    """Effective warm-up grace; honors `PULSAI_OBSERVABILITY_WARMUP_GRACE_SECONDS`."""
    import os

    raw = os.environ.get("PULSAI_OBSERVABILITY_WARMUP_GRACE_SECONDS", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return WARMUP_GRACE_SECONDS


_redis_lock = threading.Lock()
_redis_op_duration_histogram: Any = None


@dataclass
class _TimedRedisValue:
    at: Any
    command: str
    value: float


@dataclass
class _RedisWindowState:
    observations: list[_TimedRedisValue] = field(default_factory=list)


_redis_window_state = _RedisWindowState()


_KNOWN_SET = set(KNOWN_REDIS_COMMANDS)


@dataclass(frozen=True)
class RedisCompactThresholds:
    """Per-command p95 thresholds for status badges in the compact view.

    Single shared band for all commands — per-command override would be
    premature. Defaults are env-resolved at instantiation so co-located dev
    and networked prod tune independently (SoT:
    ``observability_metrics.resolve_redis_op_p95_*``); a stale module-import
    snapshot would freeze the wrong band for the process lifetime.
    """

    op_p95_warn_seconds: float = field(default_factory=resolve_redis_op_p95_warn_seconds)
    op_p95_critical_seconds: float = field(default_factory=resolve_redis_op_p95_critical_seconds)


def _trim_old(now: Any) -> None:
    _redis_window_state.observations = trim_old_observations(_redis_window_state.observations, now)


#: The distinct command names that landed in OTHER, so the bucket can explain itself.
#:
#: MEASURED on prod 2026-09-06, while the owner reported a page on every dashboard load:
#: `redis OTHER n=25 p50 0.031s p95 1.165s p99 1.421s CRITICAL`. A Redis command over a second
#: matters twice over -- Redis is single-threaded, so one slow command delays every other client,
#: and the page then names whichever dependency happened to be awaiting. This module has already
#: produced exactly that false cause once (2026-08-07: paged at GET p95=0.425s while Redis itself
#: measured 5.47 ms).
#:
#: With 24 commands labelled and everything else collapsed into one bucket, OTHER was
#: unfalsifiable: no way to tell SETEX from a pipeline from a keyspace scan. Guessing was tried
#: first and cost real time -- `scan_keys` looked like the culprit and its only caller turned out
#: to be an admin IP listing, nowhere near a chart.
#:
#: NOT A PROMETHEUS LABEL, which this module's docstring forbids and which would explode series
#: cardinality. This is a bounded diagnostic field in the compact view, exactly like
#: `synthetic_samples_dropped` beside it.
_unlabelled_redis_commands: set[str] = set()

#: DERIVED, not picked: never remember more unlabelled names than there are labelled ones. A
#: metrics module must not grow without bound because a caller issues a novel command per request.
_UNLABELLED_COMMAND_CAPACITY = len(KNOWN_REDIS_COMMANDS)


def unlabelled_redis_commands() -> tuple[str, ...]:
    """Distinct command names that fell into OTHER, sorted for a stable read."""
    with _redis_lock:
        return tuple(sorted(_unlabelled_redis_commands))


def reset_unlabelled_redis_commands_for_tests() -> None:
    """Forget the recorded OTHER command names (unit tests only)."""
    with _redis_lock:
        _unlabelled_redis_commands.clear()


def _classify_redis_command(command: str) -> str:
    """Map a Redis command name to a low-cardinality label, remembering unlabelled names."""
    if not command:
        return OTHER_LABEL
    upper = command.upper()
    if upper in _KNOWN_SET:
        return upper
    with _redis_lock:
        if len(_unlabelled_redis_commands) < _UNLABELLED_COMMAND_CAPACITY:
            _unlabelled_redis_commands.add(upper)
    return OTHER_LABEL


#: How many Redis observations were dropped for belonging to a synthetic probe request.
#:
#: Published in the compact view so the exclusion is VISIBLE — see the db counterpart. Redis
#: is the source that made this necessary twice: on 2026-08-07 it was PAGED at
#: `GET p95=0.425s` while measuring 5.47 ms, because the loop was starved. A source that has
#: already reported one false cause must not gain a silent filter as well.
_synthetic_redis_samples_dropped: int = 0


def _note_synthetic_redis_sample_dropped() -> None:
    """Count one dropped probe-caused observation."""
    global _synthetic_redis_samples_dropped
    with _redis_lock:
        _synthetic_redis_samples_dropped += 1


def synthetic_redis_samples_dropped() -> int:
    """How many Redis observations were excluded as synthetic since process start."""
    with _redis_lock:
        return _synthetic_redis_samples_dropped


def reset_synthetic_redis_samples_dropped_for_tests() -> None:
    """Zero the drop counter (unit tests only)."""
    global _synthetic_redis_samples_dropped
    with _redis_lock:
        _synthetic_redis_samples_dropped = 0


def observe_redis_op_duration_seconds(command: str, duration_seconds: float) -> None:
    """Record one Redis op into the windowed deque and Prometheus histogram.

    During the warm-up grace window (first `WARMUP_GRACE_SECONDS` after
    process start), observations are dropped — connection pools are warming
    and the samples would skew p50/p95/p99 (Finding E).

    Work caused by a SYNTHETIC PROBE is dropped for the same reason: it is not user traffic and
    it must not page. Measured 2026-09-06, while the agent probed prod authenticated:
    `redis GET critical p95=0.462s`, `redis EXISTS critical p95=0.235s` — with the endpoint
    view already excluding the same requests. Counted, not silently dropped, so an exclusion
    can never masquerade as health.
    """
    if _seconds_since_process_start() < _warmup_grace_seconds():
        return
    if is_current_request_synthetic():
        _note_synthetic_redis_sample_dropped()
        return
    if duration_seconds < 0:
        duration_seconds = 0.0

    with _redis_lock:
        now = utc_now()
        _redis_window_state.observations.append(_TimedRedisValue(at=now, command=command, value=duration_seconds))
        _trim_old(now)

    global _redis_op_duration_histogram
    try:
        from prometheus_client import Histogram
    except ImportError:
        return

    with _redis_lock:
        if _redis_op_duration_histogram is None:
            _redis_op_duration_histogram = Histogram(
                "pulsai_redis_op_duration_seconds",
                "Redis command duration grouped by command kind.",
                labelnames=("command",),
                buckets=REDIS_DURATION_HISTOGRAM_BUCKETS_SECONDS,
            )
    _redis_op_duration_histogram.labels(command=command).observe(duration_seconds)


_WRAPPER_SENTINEL_ATTR = "_pulsai_metrics_installed"


def install_redis_command_wrapper(client: Any) -> None:
    """Wrap `client.execute_command` to time + classify; idempotent per-client."""
    if getattr(client, _WRAPPER_SENTINEL_ATTR, False):
        return

    original = client.execute_command

    @functools.wraps(original)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        command = _classify_redis_command(args[0] if args else "")
        start = perf_counter()
        try:
            return await original(*args, **kwargs)
        finally:
            observe_redis_op_duration_seconds(command, perf_counter() - start)

    client.execute_command = wrapped
    setattr(client, _WRAPPER_SENTINEL_ATTR, True)


def get_redis_compact_health_view(
    *,
    now: Any | None = None,
    metric_windows: tuple[tuple[str, int], ...] | None = None,
    thresholds: RedisCompactThresholds | None = None,
) -> dict[str, Any]:
    """Return compact percentile view: windows x commands -> {count, p50, p95, p99, status}."""
    window_minutes: dict[str, int] = dict(metric_windows or OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES)
    now_dt = utc_now() if now is None else now
    th = thresholds or RedisCompactThresholds()

    with _redis_lock:
        _trim_old(now_dt)
        snapshot = list(_redis_window_state.observations)

    commands = (*KNOWN_REDIS_COMMANDS, OTHER_LABEL)
    by_label: dict[str, dict[str, dict[str, Any]]] = {}
    for window_key, minutes in window_minutes.items():
        floor = now_dt - timedelta(minutes=minutes)
        by_cmd: dict[str, dict[str, Any]] = {}
        for cmd in commands:
            values = [o.value for o in snapshot if o.at >= floor and o.command == cmd]
            percentiles = compute_percentiles(values)
            by_cmd[cmd] = {
                "count": len(values),
                **percentiles,
                "status": compute_threshold_status(
                    percentiles["p95"],
                    warn=th.op_p95_warn_seconds,
                    critical=th.op_p95_critical_seconds,
                ),
            }
        by_label[window_key] = by_cmd

    primary_window_key = next(iter(window_minutes.keys()))
    return {
        "windows": list(window_minutes.keys()),
        "primary_window": primary_window_key,
        "by_label": by_label,
        # Published for the same reason as the db counterpart: an exclusion nobody can see is
        # how a real regression hides. Redis has already produced one false cause here
        # (2026-08-07, paged at GET p95=0.425s while measuring 5.47 ms), so it is the last
        # source that should gain a silent filter.
        "synthetic_samples_dropped": synthetic_redis_samples_dropped(),
        # WHAT LANDED IN OTHER. Recorded and never published would be the inert-value defect
        # this repo has shipped twice; an OTHER bucket that goes CRITICAL without naming a
        # command is a page nobody can act on.
        "other_commands_seen": list(unlabelled_redis_commands()),
    }


__all__ = [
    "get_redis_compact_health_view",
    "install_redis_command_wrapper",
    "observe_redis_op_duration_seconds",
    "reset_synthetic_redis_samples_dropped_for_tests",
    "reset_unlabelled_redis_commands_for_tests",
    "synthetic_redis_samples_dropped",
    "unlabelled_redis_commands",
]
