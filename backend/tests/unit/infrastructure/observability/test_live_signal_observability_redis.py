"""Redis-backed live-signal observation buffer (worker write, API read)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import fakeredis
import pytest

from src.infrastructure.observability import live_signal_metrics as metrics
from src.infrastructure.observability.live_signal_metrics import get_live_signal_compact_health_view
from src.infrastructure.observability.live_signal_observability_redis import (
    append_ohlcv_tier_sample_sync,
    append_persist_commit_sample_sync,
    append_queue_wait_sample_sync,
    load_metrics_window_state_from_redis_sync,
)
from src.shared.constants.spike_alert import COMPACT_STATUS_UNKNOWN
from src.shared.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> Iterator[fakeredis.FakeRedis]:
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(
        "src.infrastructure.cache.redis_connections.create_sync_redis_client",
        lambda **_: client,
    )
    yield client
    client.flushall()


def test_redis_roundtrip_queue_wait_and_tier(fake_redis: fakeredis.FakeRedis) -> None:
    """GIVEN worker appends samples WHEN API loads THEN compact view has percentiles."""
    metrics._metrics_window_state = metrics._MetricsWindowState()
    append_queue_wait_sample_sync(0.1)
    append_queue_wait_sample_sync(0.2)
    append_persist_commit_sample_sync(0.03, timeframe="5m")
    append_ohlcv_tier_sample_sync("redis_namespaced", timeframe="5m")

    loaded = load_metrics_window_state_from_redis_sync()
    assert len(loaded.queue_wait_observations) == 2
    assert len(loaded.persist_commit_observations) == 1
    assert len(loaded.ohlcv_tier_events) == 1

    view = get_live_signal_compact_health_view(
        thresholds=metrics.LiveSignalCompactThresholds(
            queue_wait_warn_seconds=0.5,
            queue_wait_critical_seconds=1.0,
            persist_commit_warn_seconds=0.1,
            persist_commit_critical_seconds=0.2,
            persist_error_rate_warn=0.05,
            persist_error_rate_critical=0.2,
        ),
        production_timeframes=["5m"],
    )
    assert view["queue_wait"]["windows"]["15m"]["count"] >= 2
    assert view["queue_wait"]["windows"]["15m"]["p50"] is not None
    assert view["ohlcv_tier_ratio"]["windows"]["15m"]["total"] >= 1


def test_compact_view_unknown_status_when_no_samples(fake_redis: fakeredis.FakeRedis) -> None:
    """GIVEN no Redis or in-process samples THEN status is unknown (not misleading ok)."""
    metrics._metrics_window_state = metrics._MetricsWindowState()
    view = get_live_signal_compact_health_view(
        thresholds=metrics.LiveSignalCompactThresholds(
            queue_wait_warn_seconds=0.5,
            queue_wait_critical_seconds=1.0,
            persist_commit_warn_seconds=0.1,
            persist_commit_critical_seconds=0.2,
            persist_error_rate_warn=0.05,
            persist_error_rate_critical=0.2,
        ),
    )
    assert view["queue_wait"]["status"] == COMPACT_STATUS_UNKNOWN
    assert view["ohlcv_tier_ratio"]["windows"]["15m"]["redis_namespaced_ratio"] is None


def test_compact_view_excludes_stale_redis_samples(fake_redis: fakeredis.FakeRedis) -> None:
    """GIVEN old Redis samples WHEN building view THEN outside retention window ignored."""
    metrics._metrics_window_state = metrics._MetricsWindowState()
    now = utc_now()
    old = now - timedelta(hours=2)
    metrics._metrics_window_state.queue_wait_observations.append(metrics._TimedValue(at=old, value=9.0))
    view = get_live_signal_compact_health_view(
        now=now,
        thresholds=metrics.LiveSignalCompactThresholds(
            queue_wait_warn_seconds=0.5,
            queue_wait_critical_seconds=1.0,
            persist_commit_warn_seconds=0.1,
            persist_commit_critical_seconds=0.2,
            persist_error_rate_warn=0.05,
            persist_error_rate_critical=0.2,
        ),
    )
    assert view["queue_wait"]["windows"]["15m"]["count"] == 0
