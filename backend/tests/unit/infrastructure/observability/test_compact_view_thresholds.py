"""
RED tests for threshold-based status badges on DB + Redis compact views.

Behavior contract:
- A shared `compute_threshold_status(value, warn, critical) -> 'ok' | 'warn'
  | 'critical' | 'unknown'` classifies a single percentile against bands.
- `get_db_compact_health_view(..., thresholds=DbCompactThresholds(...))` adds
  a `status` field to each {operation, window} cell based on p95 vs.
  per-operation thresholds.
- `get_redis_compact_health_view(..., thresholds=RedisCompactThresholds(...))`
  does the same per-command, keyed off p95.
- Empty cells (count=0, p95=None) return status='unknown'.
- Thresholds have safe defaults; callers may override.
"""

from __future__ import annotations

import pytest

from src.infrastructure.observability import db_metrics, redis_metrics
from src.infrastructure.observability._compact_view_helpers import compute_threshold_status
from src.shared.utils.datetime_utils import utc_now


class TestComputeThresholdStatus:
    def test_value_below_warn_is_ok(self) -> None:
        assert compute_threshold_status(0.05, warn=0.1, critical=0.5) == "ok"

    def test_value_at_warn_is_warn(self) -> None:
        assert compute_threshold_status(0.1, warn=0.1, critical=0.5) == "warn"

    def test_value_between_warn_and_critical_is_warn(self) -> None:
        assert compute_threshold_status(0.25, warn=0.1, critical=0.5) == "warn"

    def test_value_at_critical_is_critical(self) -> None:
        assert compute_threshold_status(0.5, warn=0.1, critical=0.5) == "critical"

    def test_value_above_critical_is_critical(self) -> None:
        assert compute_threshold_status(2.0, warn=0.1, critical=0.5) == "critical"

    def test_none_is_unknown(self) -> None:
        assert compute_threshold_status(None, warn=0.1, critical=0.5) == "unknown"


@pytest.fixture(autouse=True)
def _reset_window_state(monkeypatch: pytest.MonkeyPatch) -> None:
    db_metrics._db_window_state = db_metrics._DbWindowState()
    redis_metrics._redis_window_state = redis_metrics._RedisWindowState()
    monkeypatch.setattr(db_metrics, "_warmup_grace_seconds", lambda: 0.0)
    monkeypatch.setattr(redis_metrics, "_warmup_grace_seconds", lambda: 0.0)


class TestDbCompactViewStatusBadges:
    def test_status_field_present_per_cell(self) -> None:
        now = utc_now()
        # Inject a fast SELECT
        db_metrics._db_window_state.observations.append(db_metrics._TimedDbValue(at=now, operation="SELECT", value=0.005))
        view = db_metrics.get_db_compact_health_view(now=now)
        primary = view["primary_window"]
        select_cell = view["by_label"][primary]["SELECT"]
        assert "status" in select_cell
        assert select_cell["status"] in {"ok", "warn", "critical", "unknown"}

    def test_fast_query_is_ok(self) -> None:
        now = utc_now()
        for _ in range(5):
            db_metrics._db_window_state.observations.append(db_metrics._TimedDbValue(at=now, operation="SELECT", value=0.005))
        view = db_metrics.get_db_compact_health_view(now=now)
        primary = view["primary_window"]
        assert view["by_label"][primary]["SELECT"]["status"] == "ok"

    def test_slow_query_is_critical(self) -> None:
        now = utc_now()
        # Two seconds is well above the SELECT critical threshold.
        for _ in range(5):
            db_metrics._db_window_state.observations.append(db_metrics._TimedDbValue(at=now, operation="SELECT", value=2.0))
        view = db_metrics.get_db_compact_health_view(now=now)
        primary = view["primary_window"]
        assert view["by_label"][primary]["SELECT"]["status"] == "critical"

    def test_empty_cell_is_unknown(self) -> None:
        view = db_metrics.get_db_compact_health_view()
        primary = view["primary_window"]
        assert view["by_label"][primary]["DELETE"]["status"] == "unknown"

    def test_custom_thresholds_override_defaults(self) -> None:
        now = utc_now()
        for _ in range(5):
            db_metrics._db_window_state.observations.append(db_metrics._TimedDbValue(at=now, operation="SELECT", value=0.05))
        very_strict = db_metrics.DbCompactThresholds(
            select_p95_warn_seconds=0.001,
            select_p95_critical_seconds=0.01,
        )
        view = db_metrics.get_db_compact_health_view(now=now, thresholds=very_strict)
        primary = view["primary_window"]
        assert view["by_label"][primary]["SELECT"]["status"] == "critical"


class TestRedisCompactViewStatusBadges:
    def test_status_field_present_per_cell(self) -> None:
        now = utc_now()
        redis_metrics._redis_window_state.observations.append(redis_metrics._TimedRedisValue(at=now, command="GET", value=0.001))
        view = redis_metrics.get_redis_compact_health_view(now=now)
        primary = view["primary_window"]
        assert "status" in view["by_label"][primary]["GET"]

    def test_fast_op_is_ok(self) -> None:
        now = utc_now()
        for _ in range(5):
            redis_metrics._redis_window_state.observations.append(redis_metrics._TimedRedisValue(at=now, command="GET", value=0.002))
        view = redis_metrics.get_redis_compact_health_view(now=now)
        primary = view["primary_window"]
        assert view["by_label"][primary]["GET"]["status"] == "ok"

    def test_slow_op_is_critical(self) -> None:
        now = utc_now()
        for _ in range(5):
            redis_metrics._redis_window_state.observations.append(redis_metrics._TimedRedisValue(at=now, command="EXISTS", value=0.5))
        view = redis_metrics.get_redis_compact_health_view(now=now)
        primary = view["primary_window"]
        assert view["by_label"][primary]["EXISTS"]["status"] == "critical"

    def test_empty_cell_is_unknown(self) -> None:
        view = redis_metrics.get_redis_compact_health_view()
        primary = view["primary_window"]
        assert view["by_label"][primary]["DEL"]["status"] == "unknown"
