"""
RED tests for the warm-up grace period (Finding E).

Behavior contract:
- During the first `WARMUP_GRACE_SECONDS` after process start, observations
  are NOT recorded into the windowed deque OR the Prometheus histogram.
  Rationale: connection pools warm across multiple connections; each cold
  connection's first op pays setup cost that pollutes p50/p95/p99.
- After the grace window elapses, observations resume normally.
- The grace is gated by `PULSAI_OBSERVABILITY_WARMUP_GRACE_SECONDS` env var
  (default WARMUP_GRACE_SECONDS), allowing 0 in tests/CI where reload
  churn is not a factor.
- Applies symmetrically to db_metrics and redis_metrics.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.infrastructure.observability import db_metrics, redis_metrics


@pytest.fixture(autouse=True)
def _reset_window_state() -> None:
    db_metrics._db_window_state = db_metrics._DbWindowState()
    redis_metrics._redis_window_state = redis_metrics._RedisWindowState()


class TestDbWarmupGrace:
    def test_observation_during_grace_is_dropped(self) -> None:
        """An observation within the grace window does NOT touch the deque."""
        # Pretend we're 1 second after process start; grace = 5 seconds.
        with (
            patch.object(db_metrics, "_seconds_since_process_start", return_value=1.0),
            patch.object(db_metrics, "_warmup_grace_seconds", return_value=5.0),
        ):
            db_metrics.observe_db_query_duration_seconds("SELECT", 0.01)
        assert db_metrics._db_window_state.observations == []

    def test_observation_after_grace_is_recorded(self) -> None:
        with (
            patch.object(db_metrics, "_seconds_since_process_start", return_value=10.0),
            patch.object(db_metrics, "_warmup_grace_seconds", return_value=5.0),
        ):
            db_metrics.observe_db_query_duration_seconds("SELECT", 0.01)
        assert len(db_metrics._db_window_state.observations) == 1

    def test_grace_zero_disables_the_gate(self) -> None:
        """Setting grace=0 means every observation is recorded immediately."""
        with (
            patch.object(db_metrics, "_seconds_since_process_start", return_value=0.001),
            patch.object(db_metrics, "_warmup_grace_seconds", return_value=0.0),
        ):
            db_metrics.observe_db_query_duration_seconds("SELECT", 0.01)
        assert len(db_metrics._db_window_state.observations) == 1


class TestRedisWarmupGrace:
    def test_observation_during_grace_is_dropped(self) -> None:
        with (
            patch.object(redis_metrics, "_seconds_since_process_start", return_value=1.0),
            patch.object(redis_metrics, "_warmup_grace_seconds", return_value=5.0),
        ):
            redis_metrics.observe_redis_op_duration_seconds("GET", 0.001)
        assert redis_metrics._redis_window_state.observations == []

    def test_observation_after_grace_is_recorded(self) -> None:
        with (
            patch.object(redis_metrics, "_seconds_since_process_start", return_value=10.0),
            patch.object(redis_metrics, "_warmup_grace_seconds", return_value=5.0),
        ):
            redis_metrics.observe_redis_op_duration_seconds("GET", 0.001)
        assert len(redis_metrics._redis_window_state.observations) == 1

    def test_grace_zero_disables_the_gate(self) -> None:
        with (
            patch.object(redis_metrics, "_seconds_since_process_start", return_value=0.001),
            patch.object(redis_metrics, "_warmup_grace_seconds", return_value=0.0),
        ):
            redis_metrics.observe_redis_op_duration_seconds("GET", 0.001)
        assert len(redis_metrics._redis_window_state.observations) == 1
