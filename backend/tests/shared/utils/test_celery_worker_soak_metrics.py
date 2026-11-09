"""BEHAVIOR: soak harness threshold evaluation."""

from __future__ import annotations

from src.shared.utils.celery_worker_soak_metrics import (
    SoakSnapshot,
    soak_delta_exceeds_threshold,
)


def test_soak_delta_passes_when_within_thresholds() -> None:
    before = SoakSnapshot(threads=10, rss_mb=100.0)
    after = SoakSnapshot(threads=12, rss_mb=120.0)

    exceeded, reason = soak_delta_exceeds_threshold(
        before,
        after,
        max_thread_delta=12,
        max_rss_mb_delta=64.0,
    )

    assert exceeded is False
    assert reason == ""


def test_soak_delta_fails_when_thread_growth_exceeds_cap() -> None:
    before = SoakSnapshot(threads=10, rss_mb=100.0)
    after = SoakSnapshot(threads=30, rss_mb=100.0)

    exceeded, reason = soak_delta_exceeds_threshold(
        before,
        after,
        max_thread_delta=5,
        max_rss_mb_delta=64.0,
    )

    assert exceeded is True
    assert "thread" in reason.lower()


def test_soak_delta_fails_when_rss_growth_exceeds_cap() -> None:
    before = SoakSnapshot(threads=10, rss_mb=100.0)
    after = SoakSnapshot(threads=10, rss_mb=200.0)

    exceeded, reason = soak_delta_exceeds_threshold(
        before,
        after,
        max_thread_delta=12,
        max_rss_mb_delta=50.0,
    )

    assert exceeded is True
    assert "rss" in reason.lower()
