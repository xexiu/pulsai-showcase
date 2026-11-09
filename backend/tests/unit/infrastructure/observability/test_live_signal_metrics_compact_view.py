from __future__ import annotations

from datetime import timedelta

from src.infrastructure.observability import live_signal_metrics as metrics
from src.shared.utils.datetime_utils import utc_now


def test_compact_view_exposes_percentiles_ratios_and_badges() -> None:
    now = utc_now()
    metrics._metrics_window_state = metrics._MetricsWindowState()

    for value in [0.05, 0.1, 0.2, 0.6]:
        metrics._metrics_window_state.queue_wait_observations.append(metrics._TimedValue(at=now, value=value))
    for value in [0.01, 0.03, 0.2]:
        metrics._metrics_window_state.persist_commit_observations.append(metrics._TimedValue(at=now, value=value))
    metrics._metrics_window_state.persist_commit_errors.append(metrics._TimedValue(at=now, value=1.0))
    metrics._metrics_window_state.ohlcv_tier_events.extend(
        [
            metrics._TimedTier(at=now, tier="redis_namespaced"),
            metrics._TimedTier(at=now, tier="redis_namespaced"),
            metrics._TimedTier(at=now, tier="exchange_namespaced"),
        ]
    )

    view = metrics.get_live_signal_compact_health_view(
        now=now,
        production_timeframes=["5m", "1h"],
        thresholds=metrics.LiveSignalCompactThresholds(
            queue_wait_warn_seconds=0.2,
            queue_wait_critical_seconds=0.5,
            persist_commit_warn_seconds=0.1,
            persist_commit_critical_seconds=0.15,
            persist_error_rate_warn=0.05,
            persist_error_rate_critical=0.2,
        ),
    )

    assert view["windows"] == ["15m", "1h"]
    assert "15m" in view["queue_wait"]["windows"]
    assert "1h" in view["queue_wait"]["windows"]
    assert view["ohlcv_tier_ratio"]["windows"]["15m"]["redis_namespaced_ratio"] > 0
    assert view["persist_commit"]["windows"]["15m"]["error_rate"] > 0
    assert view["persist_commit"]["status"] in {"ok", "warn", "critical"}
    assert "by_timeframe" in view["persist_commit"]
    assert "5m" in view["persist_commit"]["by_timeframe"]["15m"]
    assert "1h" in view["persist_commit"]["by_timeframe"]["15m"]
    assert "by_timeframe" in view["ohlcv_tier_ratio"]
    assert "5m" in view["ohlcv_tier_ratio"]["by_timeframe"]["15m"]
    assert "1h" in view["ohlcv_tier_ratio"]["by_timeframe"]["15m"]


def test_compact_view_excludes_stale_events_from_windows() -> None:
    now = utc_now()
    old = now - timedelta(hours=2)
    metrics._metrics_window_state = metrics._MetricsWindowState()
    metrics._metrics_window_state.queue_wait_observations.append(metrics._TimedValue(at=old, value=1.0))

    view = metrics.get_live_signal_compact_health_view(
        now=now,
        production_timeframes=["5m"],
        thresholds=metrics.LiveSignalCompactThresholds(
            queue_wait_warn_seconds=0.2,
            queue_wait_critical_seconds=0.5,
            persist_commit_warn_seconds=0.1,
            persist_commit_critical_seconds=0.15,
            persist_error_rate_warn=0.05,
            persist_error_rate_critical=0.2,
        ),
    )
    assert view["queue_wait"]["windows"]["15m"]["count"] == 0
    assert view["queue_wait"]["windows"]["1h"]["count"] == 0


def test_compact_view_metric_windows_override_changes_payload_keys() -> None:
    now = utc_now()
    metrics._metrics_window_state = metrics._MetricsWindowState()

    view = metrics.get_live_signal_compact_health_view(
        now=now,
        production_timeframes=[],
        metric_windows=(("5m", 5), ("4h", 240)),
        thresholds=metrics.LiveSignalCompactThresholds(
            queue_wait_warn_seconds=0.2,
            queue_wait_critical_seconds=0.5,
            persist_commit_warn_seconds=0.1,
            persist_commit_critical_seconds=0.15,
            persist_error_rate_warn=0.05,
            persist_error_rate_critical=0.2,
        ),
    )

    assert view["windows"] == ["5m", "4h"]
    assert view["primary_window"] == "5m"
    assert set(view["queue_wait"]["windows"].keys()) == {"5m", "4h"}
    assert set(view["persist_commit"]["windows"].keys()) == {"5m", "4h"}
