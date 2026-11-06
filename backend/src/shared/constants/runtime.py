"""
Shared runtime namespace constants for Redis/Celery integration points.

WHY this module exists:
- Workers, admin use cases, pub/sub, and beat scheduling all share the same
  Redis namespace contract
- Keeping key formats here avoids silent drift between producers, consumers,
  cleanup flows, and runtime inspection tooling
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

PULSAI_RUNTIME_NAMESPACE: Final[str] = "pulsai"

SCHEDULE_CONFIG_REDIS_KEY: Final[str] = f"{PULSAI_RUNTIME_NAMESPACE}:scheduled_tasks:enabled"
SIGNAL_PUBSUB_CHANNEL: Final[str] = f"{PULSAI_RUNTIME_NAMESPACE}:signals"
# Phase 4: Celery→FE bridge for venue lifecycle events. Celery worker publishes
# OrderFilled / PositionClosed / PositionMarkUpdated JSON payloads here; FastAPI
# lifespan subscribes and fans out via ``ConnectionManager.broadcast_lifecycle_event``.
LIFECYCLE_EVENT_PUBSUB_CHANNEL: Final[str] = f"{PULSAI_RUNTIME_NAMESPACE}:lifecycle_events"
# Promote/rollback: API publishes; Celery children subscribe and drop in-process bundles.
MODEL_CACHE_INVALIDATE_CHANNEL: Final[str] = f"{PULSAI_RUNTIME_NAMESPACE}:model_cache_invalidate"
# SoT: long-lived Redis pub/sub listeners (FastAPI lifespan, Celery daemon thread, OHLCV supervisor).
REDIS_PUBSUB_RECONNECT_DELAY_SECONDS: Final[int] = 5
TRAINING_LOCK_KEY_PREFIX: Final[str] = f"{PULSAI_RUNTIME_NAMESPACE}:training:lock:"
TRAINING_LOCK_SCAN_PATTERN: Final[str] = f"{TRAINING_LOCK_KEY_PREFIX}*"
REDBEAT_KEY_PREFIX: Final[str] = f"{PULSAI_RUNTIME_NAMESPACE}:beat:"
# Claims an in-flight hunt-loop run so a second identical request joins it instead of stacking
# another copy on the training queue. See ``build_hunt_loop_claim_key``.
HUNT_LOOP_CLAIM_KEY_PREFIX: Final[str] = f"{PULSAI_RUNTIME_NAMESPACE}:hunt_loop:claim:"
# Backstop only. The claim is released when the task finishes, so this bounds how long a run that
# died without releasing (worker SIGSEGV, container kill) can block a legitimate re-request. Sized
# well above a real hunt: a seasonality run on the LOW grid measured 952s, and the HTF band is
# longer, so a few hours of headroom keeps the backstop from firing on healthy work.
HUNT_LOOP_CLAIM_TTL_SECONDS: Final[int] = 6 * 60 * 60

# Kept as-is for backward compatibility with existing live retry locks.
RETRY_LOCK_KEY_PREFIX: Final[str] = "retry_lock:"
RETRY_LOCK_SCAN_PATTERN: Final[str] = f"{RETRY_LOCK_KEY_PREFIX}*"
RETRY_LOCK_TTL_SECONDS: Final[int] = 5


def is_testing_runtime() -> bool:
    """Return True when the current process runs under TESTING=true."""
    return os.environ.get("TESTING", "").lower() == "true"


def redis_runtime_namespace() -> str:
    """Return the Redis namespace for the current runtime tier."""
    if is_testing_runtime():
        return f"{PULSAI_RUNTIME_NAMESPACE}:test"
    return PULSAI_RUNTIME_NAMESPACE


def namespaced_runtime_redis_key(key: str) -> str:
    """Prefix a logical Redis key so tests and local dev do not share state."""
    namespace = redis_runtime_namespace()
    if key.startswith(f"{namespace}:"):
        return key
    return f"{namespace}:{key}"


def build_training_lock_key(suffix: str) -> str:
    """Return the Redis key used to deduplicate training runs."""
    return f"{TRAINING_LOCK_KEY_PREFIX}{suffix}"


def build_retry_lock_key(job_id: str) -> str:
    """Return the Redis key used to throttle retry requeue requests."""
    return f"{RETRY_LOCK_KEY_PREFIX}{job_id}"


def build_hunt_loop_claim_key(
    hypothesis: str, *, high_timeframes: bool, apply: bool, timeframes: Sequence[str] | None = None, fee_schedule: str | None = None
) -> str:
    """Return the Redis key claiming an in-flight hunt-loop run.

    Keyed on the WHOLE triple the worker runs with, not the hypothesis alone. ``run_hunt_loop_now``
    takes ``high_timeframes`` and ``apply`` as per-run arguments bound at enqueue, so a dry run and
    an applying run of the same hypothesis are different work and must not deduplicate against each
    other.

    MEASURED 2026-08-30: 18 of 21 queued ``run_hunt_loop_now`` messages were the identical
    ``('seasonality', high=True, apply=True)`` triple - 21 distinct task ids, ``retries=0``, from 9
    API processes, so genuinely 18 separate enqueues rather than redeliveries. Two capital-cert
    messages sat behind them.

    Name is normalised (stripped, lowercased) so a stray space or capital cannot open a second
    claim on work that is already running.
    """
    normalised = hypothesis.strip().lower()
    band = "high" if high_timeframes else "low"
    mode = "apply" if apply else "dry"
    key = f"{HUNT_LOOP_CLAIM_KEY_PREFIX}{normalised}:{band}:{mode}"
    # A run that NAMES its timeframes (one slot of a slow hypothesis) is different work from the band
    # preset and from every other slot, so it claims its own key.
    if timeframes is not None:
        key = f"{key}:tf={','.join(timeframes)}"
    # A run graded at a NAMED fee schedule is different work from one charging the worker's own setting.
    if fee_schedule is not None:
        key = f"{key}:fee={fee_schedule}"
    return key


def hunt_loop_run_scope(timeframes: Sequence[str] | None, time_budget_seconds: float | None) -> dict[str, object]:
    """The per-run scope a caller NAMED, and nothing else -- the ONE home for the run-loop route's message
    and the task's runner call.

    Only named keys travel, so an unscoped run is byte-identical to one enqueued before the scope existed:
    the API and the worker deploy separately, and a worker still on the old code would reject an
    unexpected keyword on EVERY run, not only on the scoped ones.
    """
    scope: dict[str, object] = {}
    if timeframes is not None:
        scope["timeframes"] = list(timeframes)
    if time_budget_seconds is not None:
        scope["time_budget_seconds"] = time_budget_seconds
    return scope
