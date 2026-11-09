"""Behavior tests for the solo-pool RSS watchdog.

WHY: ``worker_max_memory_per_child`` recycles prefork *children* by RSS, but it is
a no-op for ``--pool=solo`` workers (monitoring, ohlcv_stream) which run tasks
inline in the main process with no child to recycle. Those workers therefore have
NO memory guard and grow unbounded (observed: monitoring 261 MB import -> 2.8 GB
resident on Railway). This watchdog is the solo-pool equivalent: after each task it
checks resident memory and, above the cap, requests a warm shutdown so the
``restartPolicyType: ALWAYS`` supervisor respawns a fresh worker.

@see src/workers/celery_solo_rss_watchdog.py
@see docs/06-devops/PERFORMANCE_MONITORING.md § solo-pool memory guard
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.infrastructure.config.settings_sections.settings_ops_workers import (
    CELERY_SOLO_GROWTH_HEADROOM_KIB,
    CELERY_SOLO_POST_MODEL_BASELINE_KIB,
)
from src.shared.constants.celery import CELERY_SOLO_RSS_WATCHDOG_MAX_KIB
from src.workers import celery_solo_rss_watchdog as wd


@pytest.fixture(autouse=True)
def _isolate_watchdog_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep each test from leaking a connected signal or a real SIGTERM."""
    monkeypatch.setattr(wd, "_WATCHDOG_CAP_KIB", 0, raising=False)
    monkeypatch.setattr(wd, "_shutdown_requested", False, raising=False)
    monkeypatch.setattr(wd, "_recycle_pending", False, raising=False)
    # Never let a real warm shutdown fire during the suite.
    monkeypatch.setattr(wd, "_trigger_warm_shutdown", lambda: None)
    yield
    wd.disarm_solo_rss_watchdog()


@pytest.mark.parametrize(
    "argv",
    [
        ["celery", "-A", "src.workers.celery_app", "worker", "--pool=solo"],
        ["celery", "worker", "--pool", "solo"],
        ["celery", "worker", "-P", "solo"],
    ],
)
def test_is_solo_pool_detects_every_cli_form(argv: list[str]) -> None:
    assert wd.is_solo_pool(argv) is True


@pytest.mark.parametrize(
    "argv",
    [
        ["celery", "worker", "--queues=training", "--concurrency=2"],  # prefork (default)
        ["celery", "worker", "--pool=prefork"],
        ["uvicorn", "src.main:app", "--workers", "1"],
        ["celery", "beat"],
        [],
    ],
)
def test_is_solo_pool_false_for_non_solo(argv: list[str]) -> None:
    assert wd.is_solo_pool(argv) is False


def test_should_recycle_true_when_at_or_above_cap() -> None:
    assert wd.should_recycle_for_rss(current_rss_kib=900_000, cap_kib=900_000) is True
    assert wd.should_recycle_for_rss(current_rss_kib=950_000, cap_kib=900_000) is True


def test_should_recycle_false_when_below_cap() -> None:
    assert wd.should_recycle_for_rss(current_rss_kib=512_000, cap_kib=900_000) is False


def test_should_recycle_disabled_when_cap_is_zero() -> None:
    """cap_kib == 0 means the guard is disabled (mirror max_memory_per_child)."""
    assert wd.should_recycle_for_rss(current_rss_kib=10_000_000, cap_kib=0) is False


def test_current_rss_kib_is_positive() -> None:
    assert wd.current_rss_kib() > 0


# THE SHUTDOWN MUST NOT PRECEDE THE ACK.
#
# MEASURED 2026-09-30 in apps/api/logs/pulsai.log: at 11:42:50 `run_hunt_loop_now[605af1a0]` FAILED
# (adx_di_ml_feat_full@4h over its 13,200 s budget) and in the same second this watchdog tripped at
# 3,198,176 KiB. The SIGTERM was sent from `task_postrun`, which Celery runs BEFORE it acks an
# `acks_late` message, and Celery's handler raises WorkerShutdown in the main thread -- so the
# FINISHED task was never acked and came back at 11:43:15 under the same id, to run the same doomed
# 3 h 40 m budget again on the only training lane. A finished task must be acked; the recycle waits
# for the NEXT task's prerun. MEASURED 2026-10-02 on a real worker: that next task still runs to
# completion and is acked (it is not redelivered); prefetched tasks are restored to the queue.


def test_postrun_over_cap_does_not_shut_down_before_the_task_is_acknowledged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(wd, "_WATCHDOG_CAP_KIB", 900_000, raising=False)
    monkeypatch.setattr(wd, "current_rss_kib", lambda: 1_200_000)
    monkeypatch.setattr(wd, "_trigger_warm_shutdown", lambda: calls.append(1))

    wd.on_task_postrun()

    assert calls == [], "a SIGTERM here lands between the finished task and its ack"


def test_the_next_tasks_prerun_recycles_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(wd, "_WATCHDOG_CAP_KIB", 900_000, raising=False)
    monkeypatch.setattr(wd, "current_rss_kib", lambda: 1_200_000)
    monkeypatch.setattr(wd, "_trigger_warm_shutdown", lambda: calls.append(1))

    wd.on_task_postrun()
    wd.on_task_prerun()
    wd.on_task_prerun()  # already shutting down: must NOT re-fire
    wd.on_task_postrun()

    assert calls == [1]


def test_prerun_does_nothing_without_a_pending_recycle(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(wd, "_WATCHDOG_CAP_KIB", 900_000, raising=False)
    monkeypatch.setattr(wd, "current_rss_kib", lambda: 1_200_000)
    monkeypatch.setattr(wd, "_trigger_warm_shutdown", lambda: calls.append(1))

    wd.on_task_prerun()

    assert calls == [], "only a task that FINISHED over the cap schedules a recycle"


def test_postrun_noop_when_under_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(wd, "_WATCHDOG_CAP_KIB", 900_000, raising=False)
    monkeypatch.setattr(wd, "current_rss_kib", lambda: 400_000)
    monkeypatch.setattr(wd, "_trigger_warm_shutdown", lambda: calls.append(1))

    wd.on_task_postrun()
    wd.on_task_prerun()

    assert calls == []


def test_postrun_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(wd, "_WATCHDOG_CAP_KIB", 0, raising=False)
    monkeypatch.setattr(wd, "current_rss_kib", lambda: 10_000_000)
    monkeypatch.setattr(wd, "_trigger_warm_shutdown", lambda: calls.append(1))

    wd.on_task_postrun()

    assert calls == []


def test_arm_returns_false_and_does_not_connect_for_non_solo() -> None:
    armed = wd.arm_solo_rss_watchdog(argv=["celery", "worker", "--concurrency=2"], cap_kib=900_000)
    assert armed is False
    assert wd._WATCHDOG_CAP_KIB == 0


def test_arm_returns_false_when_cap_disabled() -> None:
    armed = wd.arm_solo_rss_watchdog(argv=["celery", "worker", "--pool=solo"], cap_kib=0)
    assert armed is False


def test_arm_returns_true_and_sets_cap_for_solo() -> None:
    armed = wd.arm_solo_rss_watchdog(argv=["celery", "worker", "--pool=solo"], cap_kib=900_000)
    assert armed is True
    assert wd._WATCHDOG_CAP_KIB == 900_000


# THE CAP MUST SIT ABOVE THE WORKER'S OWN RESIDENT FLOOR.
#
# MEASURED 2026-08-21 on darwin/py3.11 from apps/api/logs/pulsai.log: the monitoring solo worker
# tripped the watchdog SIX times between 18:14 and 18:17 at 903, 924, 945, 1497, 1508 and 1516 MiB
# against a 900 MiB cap, and FinBERT was loaded 14 times in one log. Every sample was at or above
# the cap, so the worker recycled after every task and no work ever completed: respawn -> load
# ~1.3 GB FinBERT -> over cap -> warm shutdown -> repeat.
#
# This is the SAME defect the PREFORK cap already had and already fixed (see
# CELERY_CHILD_POST_PREWARM_BASELINE_KIB in settings_ops_workers.py, whose comment records
# "a recycle cap under the process floor cannot catch a leak; it only guarantees churn"). The fix
# here applies that established pattern rather than inventing a second mechanism.


def test_solo_cap_sits_above_the_measured_finbert_resident_floor() -> None:
    assert CELERY_SOLO_RSS_WATCHDOG_MAX_KIB > CELERY_SOLO_POST_MODEL_BASELINE_KIB, (
        "a cap below the worker's own floor recycles every task instead of catching a leak"
    )


def test_worker_holding_finbert_is_not_recycled() -> None:
    # 1,552,400 KiB = the WORST legitimate sample measured while FinBERT was resident.
    assert not wd.should_recycle_for_rss(1_552_400, CELERY_SOLO_RSS_WATCHDOG_MAX_KIB)


def test_the_training_worker_is_not_recycled_either() -> None:
    """One constant arms EVERY solo worker, so it must clear the heaviest of them.

    2_406_400 KiB, measured flat across six samples 10 s apart while the training queue was
    working. A first pass at this fix sized the cap on the monitoring floor alone (1_600_000
    baseline) and would have recycled this worker on every task -- the same defect, one worker
    over.
    """
    assert not wd.should_recycle_for_rss(2_406_400, CELERY_SOLO_RSS_WATCHDOG_MAX_KIB)


def test_every_measured_thrash_sample_would_now_survive() -> None:
    measured_kib = [924_688, 945_792, 948_528, 1_497_000, 1_527_824, 1_552_400, 2_406_400]

    recycled = [rss for rss in measured_kib if wd.should_recycle_for_rss(rss, CELERY_SOLO_RSS_WATCHDOG_MAX_KIB)]

    assert recycled == [], f"still recycling legitimate samples: {recycled}"


def test_the_railway_leak_is_still_caught() -> None:
    # The pathology this watchdog exists for: monitoring grew 261 MB import -> 2.8 GB resident.
    assert wd.should_recycle_for_rss(2_936_012, CELERY_SOLO_RSS_WATCHDOG_MAX_KIB)


def test_growth_headroom_is_bounded_so_the_guard_still_bites() -> None:
    """Headroom must not be so generous that a real leak never trips it."""
    assert CELERY_SOLO_GROWTH_HEADROOM_KIB <= 1_024_000


def test_trigger_warm_shutdown_sends_sigterm_to_self(monkeypatch: pytest.MonkeyPatch) -> None:
    """Warm shutdown must SIGTERM the worker's own PID (Celery handles graceful drain)."""
    import os
    import signal as signal_mod

    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: sent.append((pid, sig)))
    # Use the real implementation (the autouse fixture stubbed it out).
    monkeypatch.setattr(wd, "_trigger_warm_shutdown", wd._trigger_warm_shutdown_impl)

    wd._trigger_warm_shutdown()

    assert sent == [(os.getpid(), signal_mod.SIGTERM)]


def test_regression_2026_10_03_the_armed_line_is_logged_once_the_worker_is_ready(caplog: pytest.LogCaptureFixture) -> None:
    """Arming runs at celery_app import, BEFORE Celery configures logging, so its INFO line never
    reached prod: 7 monitoring deployments (10-02 09:23 -> 10-03 10:31) logged no "armed" line while
    pid 1 ran --pool=solo with a 1,600,000 KiB cap -- a guard indistinguishable from an unarmed one.
    The line is now emitted on worker_ready, when logging exists."""
    from celery.signals import worker_ready

    wd.arm_solo_rss_watchdog(argv=["celery", "worker", "--pool=solo"], cap_kib=900_000)
    with caplog.at_level("INFO", logger=wd.logger.name):
        worker_ready.send(sender=None)

    assert any("armed" in r.getMessage() and "900000 KiB" in r.getMessage() for r in caplog.records)


def test_an_unarmed_worker_announces_nothing_when_ready(caplog: pytest.LogCaptureFixture) -> None:
    from celery.signals import worker_ready

    wd.arm_solo_rss_watchdog(argv=["celery", "worker", "--concurrency=2"], cap_kib=900_000)
    with caplog.at_level("INFO", logger=wd.logger.name):
        worker_ready.send(sender=None)

    assert not any("armed" in r.getMessage() for r in caplog.records)
