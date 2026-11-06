"""Shared helpers for windowed compact percentile views (db/redis metrics).

Mirrors and consolidates the local `_percentiles` helpers in
`db_metrics.py` and `redis_metrics.py`. `live_signal_metrics.py` retains its
own version intentionally (Phase-3 SoT not in scope for this slice).
"""

from __future__ import annotations

from datetime import timedelta
from statistics import quantiles
from typing import Any, Protocol

from src.shared.constants.spike_alert import (
    COMPACT_STATUS_CRITICAL,
    COMPACT_STATUS_OK,
    COMPACT_STATUS_UNKNOWN,
    COMPACT_STATUS_WARN,
)


class _HasTimestamp(Protocol):
    at: Any


_OBSERVATION_RETENTION = timedelta(hours=1)


def trim_old_observations[T: _HasTimestamp](observations: list[T], now: Any) -> list[T]:
    """Drop observations older than the retention window (1h)."""
    floor = now - _OBSERVATION_RETENTION
    return [o for o in observations if o.at >= floor]


def compute_threshold_status(
    value: float | None,
    *,
    warn: float,
    critical: float,
) -> str:
    """Classify a percentile against {warn, critical} bands.

    Returns one of: 'ok', 'warn', 'critical', 'unknown'. `unknown` is reserved
    for empty samples (value is None) so the FE can render a neutral badge
    instead of a misleading 'ok'.
    """
    if value is None:
        return COMPACT_STATUS_UNKNOWN
    if value >= critical:
        return COMPACT_STATUS_CRITICAL
    if value >= warn:
        return COMPACT_STATUS_WARN
    return COMPACT_STATUS_OK


def compute_percentiles(values: list[float]) -> dict[str, float | None]:
    """Return {p50, p95, p99} for the given samples; nulls when no data."""
    if not values:
        return {"p50": None, "p95": None, "p99": None}
    if len(values) == 1:
        base = values[0]
        return {"p50": base, "p95": base, "p99": base}
    qs = quantiles(values, n=100, method="inclusive")
    return {"p50": qs[49], "p95": qs[94], "p99": qs[98]}
