"""Resident-memory watchdog for ``--pool=solo`` Celery workers.

WHY: ``worker_max_memory_per_child`` recycles prefork *children* once their RSS
crosses a cap, but it is a **no-op for ``--pool=solo``** workers. Solo workers run
tasks inline in the main process — there is no child to kill — so the cap never
applies and resident memory grows unbounded. PulsAI runs two solo workers
(``monitoring`` loads PyTorch/FinBERT, ``ohlcv_stream`` holds CCXT-Pro WebSockets)
for fork-safety; on Railway the monitoring worker grew from a 261 MB import
baseline to 2.8 GB resident — ~46% of the memory bill — with no guard at all.

This module is the solo-pool equivalent of ``worker_max_memory_per_child``: after
every task it samples resident memory and, above the configured cap, asks the
worker to **warm-shutdown** (``SIGTERM`` to itself) -- at the NEXT task's prerun,
never at this task's postrun. Railway's ``restartPolicyType: ALWAYS`` respawns a
fresh worker, bounding memory deterministically without any fork.

What a recycle does, MEASURED 2026-10-02 end to end on a real ``--pool=solo`` worker
(Celery 5.6.3, Redis broker, cap 1 KiB, three probe tasks; pinned by
tests/integration/workers/test_solo_watchdog_recycle_end_to_end.py): task 1 ran and
logged "tripped"; task 2's prerun sent SIGTERM ("Warm shutdown"), and task 2 STILL RAN
TO COMPLETION in the dying worker and was acknowledged -- Celery's handler only sets
``state.should_stop``, the loop raises ``WorkerShutdown`` after the current task. The
prefetched task 3 was restored at shutdown ("Restoring 1 unacknowledged message(s)")
and ran once on the next worker. Exit code 0. No task lost, none run twice. An earlier
version of this docstring said the triggering message was "redelivered unstarted"; it
is not.

Why not at postrun (MEASURED 2026-09-30, apps/api/logs/pulsai.log 11:42:50): Celery
runs ``task_postrun`` BEFORE it acks an ``acks_late`` message, and its SIGTERM
handler raises ``WorkerShutdown`` in the main thread, i.e. between the finished task
and its ack. The FINISHED task was redelivered -- a hunt slot that had just failed its
13,200 s budget came back under the same id and re-ran it on the only training lane,
a loop with no exit. Deferring to the next prerun lets the ack land first.

The cap is the SoT constant :data:`CELERY_SOLO_RSS_WATCHDOG_MAX_KIB` (env
``CELERY_SOLO_RSS_WATCHDOG_MAX_KIB``; ``0`` disables). Arming is gated on the
worker actually running ``--pool=solo`` so prefork workers (which have their own
recycler) and the API/beat processes are never touched.

@see src/workers/celery_solo_pool_compat.py — companion solo warm-shutdown patch
@see docs/06-devops/PERFORMANCE_MONITORING.md § solo-pool memory guard
@see docs/04-structural/CONCURRENCY_INVARIANTS.md — solo-pool topology rationale
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from collections.abc import Sequence
from typing import Any, Final

from celery.signals import task_postrun, task_prerun, worker_ready

from src.shared.constants.celery import CELERY_SOLO_RSS_WATCHDOG_MAX_KIB
from src.shared.utils.celery_worker_soak_metrics import rss_mb

logger = logging.getLogger(__name__)

_SOLO: Final[str] = "solo"
_POOL_FLAGS: Final[tuple[str, ...]] = ("--pool", "-P")
_POOL_EQ_PREFIX: Final[str] = "--pool="
_DISPATCH_UID: Final[str] = "pulsai.solo_rss_watchdog"
_PRERUN_DISPATCH_UID: Final[str] = "pulsai.solo_rss_watchdog.prerun"
_READY_DISPATCH_UID: Final[str] = "pulsai.solo_rss_watchdog.ready"
_KIB_PER_MIB: Final[int] = 1024

# Armed by :func:`arm_solo_rss_watchdog`; 0 = disabled (default for non-solo processes).
_WATCHDOG_CAP_KIB: int = 0
# Set at postrun when a finished task left the worker over the cap; acted on at the next prerun.
_recycle_pending: bool = False
# Latch so a worker draining toward shutdown does not re-signal on every subsequent task.
_shutdown_requested: bool = False

__all__ = [
    "arm_solo_rss_watchdog",
    "current_rss_kib",
    "disarm_solo_rss_watchdog",
    "is_solo_pool",
    "on_task_postrun",
    "on_task_prerun",
    "should_recycle_for_rss",
]


def is_solo_pool(argv: Sequence[str] | None = None) -> bool:
    """Return ``True`` when the worker's argv selects ``--pool=solo``.

    Recognises ``--pool=solo``, ``--pool solo`` and ``-P solo`` (Celery's CLI
    forms). Defaults to :data:`sys.argv` so the live worker self-detects at import.
    """
    tokens = list(sys.argv if argv is None else argv)
    for index, token in enumerate(tokens):
        if token in _POOL_FLAGS:
            following = tokens[index + 1] if index + 1 < len(tokens) else ""
            if following.strip().lower() == _SOLO:
                return True
        elif token.startswith(_POOL_EQ_PREFIX):
            if token.split("=", 1)[1].strip().lower() == _SOLO:
                return True
    return False


def current_rss_kib() -> int:
    """Current resident memory in KiB (reuses the soak-harness platform-aware reader)."""
    return int(rss_mb() * _KIB_PER_MIB)


def should_recycle_for_rss(current_rss_kib: int, cap_kib: int) -> bool:
    """Pure decision: recycle when the cap is enabled and resident memory reaches it."""
    return cap_kib > 0 and current_rss_kib >= cap_kib


def _trigger_warm_shutdown_impl() -> None:
    """Send the worker's own process a SIGTERM (Celery's warm-shutdown signal)."""
    os.kill(os.getpid(), signal.SIGTERM)


# Indirection point so tests can assert behaviour without sending a real signal.
_trigger_warm_shutdown = _trigger_warm_shutdown_impl


def on_task_postrun(*_args: Any, **_kwargs: Any) -> None:
    """``task_postrun`` handler: when the finished task left the worker over the cap, schedule a recycle.

    Never signals here -- the task is not acknowledged yet (see the module docstring).
    """
    global _recycle_pending
    if _shutdown_requested or _recycle_pending:
        return
    rss_kib = current_rss_kib()
    if not should_recycle_for_rss(rss_kib, _WATCHDOG_CAP_KIB):
        return
    _recycle_pending = True
    logger.warning(
        "solo-pool RSS watchdog tripped: resident %d KiB >= cap %d KiB — recycling the worker before the next task, once this one is acknowledged",
        rss_kib,
        _WATCHDOG_CAP_KIB,
    )


def on_task_prerun(*_args: Any, **_kwargs: Any) -> None:
    """``task_prerun`` handler: carry out a pending recycle before the next task's body runs.

    The previous task is acknowledged by now; this one has done no work, so ``acks_late``
    redelivers it to the fresh worker at no cost.
    """
    global _shutdown_requested
    if _shutdown_requested or not _recycle_pending:
        return
    _shutdown_requested = True
    logger.warning("solo-pool RSS watchdog: warm-shutting down -- this task finishes first, prefetched tasks go back to the queue")
    _trigger_warm_shutdown()


def arm_solo_rss_watchdog(
    argv: Sequence[str] | None = None,
    cap_kib: int | None = None,
) -> bool:
    """Connect the watchdog when (and only when) this process is a solo worker.

    Returns ``True`` when armed. No-op (returns ``False``) for prefork workers, the
    API/beat processes, or when the cap is disabled (``0``) — so it is safe to call
    unconditionally at ``celery_app`` import from every service.
    """
    global _WATCHDOG_CAP_KIB, _shutdown_requested, _recycle_pending
    cap = CELERY_SOLO_RSS_WATCHDOG_MAX_KIB if cap_kib is None else cap_kib
    if not is_solo_pool(argv) or cap <= 0:
        return False
    _WATCHDOG_CAP_KIB = cap
    _shutdown_requested = False
    _recycle_pending = False
    task_postrun.connect(on_task_postrun, weak=False, dispatch_uid=_DISPATCH_UID)
    task_prerun.connect(on_task_prerun, weak=False, dispatch_uid=_PRERUN_DISPATCH_UID)
    worker_ready.connect(announce_armed, weak=False, dispatch_uid=_READY_DISPATCH_UID)
    return True


def announce_armed(*_args: Any, **_kwargs: Any) -> None:
    """``worker_ready`` handler: say the watchdog is armed, now that Celery's logging exists.

    Arming runs at ``celery_app`` import, before Celery configures logging, so a line logged THERE
    never reached prod: 7 monitoring deployments (2026-10-02 09:23 -> 10-03 10:31) showed no "armed"
    line while pid 1 ran ``--pool=solo`` under a 1,600,000 KiB cap. A guard whose arming leaves no
    trace reads exactly like one that never armed.
    """
    logger.info("solo-pool RSS watchdog armed: recycle worker above %d KiB", _WATCHDOG_CAP_KIB)


def disarm_solo_rss_watchdog() -> None:
    """Disconnect the watchdog and reset state (used by tests; harmless in prod)."""
    global _WATCHDOG_CAP_KIB, _shutdown_requested, _recycle_pending
    task_postrun.disconnect(on_task_postrun, dispatch_uid=_DISPATCH_UID)
    task_prerun.disconnect(on_task_prerun, dispatch_uid=_PRERUN_DISPATCH_UID)
    worker_ready.disconnect(announce_armed, dispatch_uid=_READY_DISPATCH_UID)
    _WATCHDOG_CAP_KIB = 0
    _shutdown_requested = False
    _recycle_pending = False
