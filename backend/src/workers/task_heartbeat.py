"""A liveness heartbeat for long worker tasks, so a dead task stops looking like a working one.

IMPORTERS / CALLERS: ``src.workers.tasks.cert_run_tasks`` and
``src.workers.tasks.select_confirm_tasks`` write the beat; the admin poll mapper
``src.api.admin.research_loop_admin_routes.research_loop_celery_task_status`` reads it.
AFFECTED API: no route moves. ``CertRunStatusResponse`` gains SIX OPTIONAL fields
(heartbeat_at, heartbeat_age_seconds, heartbeat_stale, worker_code_revision, api_code_revision,
worker_code_stale — the last three added by STALEWORKER-1, see ``worker_code_revision.py``), so
every existing caller is unaffected.
DATA SCHEMAS: writes a dict into the Celery RESULT BACKEND as the meta of state ``STARTED``.
Nothing is written to Postgres and no file is touched. Keys: ``heartbeat_at`` (ISO-8601 UTC),
``heartbeat_pid`` (int), ``started_at`` (ISO-8601 UTC), ``code_revision`` (str | None, the
worker's boot git sha).

REUSE-AUDIT: considered ``src.workers.celery_solo_rss_watchdog`` — it also runs alongside a task
and also signals the worker, but it fires on ``task_postrun`` (AFTER the task ends) and its job is
to BOUND memory, not to report liveness; extending it would put two unrelated policies in one
module and still could not emit during a run. Considered
``src.shared.utils.celery_worker_soak_metrics`` — reused (``rss_mb`` is the platform-aware reader
the watchdog already uses) rather than forked, but it measures memory, not liveness. Considered
``src.shared.constants.celery`` for the two constants below and deliberately did NOT put them
there: they are read by exactly this mechanism and its reader, a second agent is editing that file
concurrently, and the interval only means anything next to the stale window it derives. Searched
for an existing heartbeat: ``update_state`` had ZERO occurrences repo-wide, so there was nothing to
extend.

WHY THIS EXISTS, measured 2026-09-21. Celery writes ``STARTED`` once, when a worker picks a task
up. Nothing rewrites it if that worker is then killed, so the result backend keeps reporting
``STARTED`` forever: cert task 22ca3e16 read STARTED for 2h20m after its worker had gone. A reader
cannot tell that from a task that is working hard, and the repo's own history shows what that
ambiguity costs — an operator reloads the worker to "unstick" it, ``task_acks_late`` redelivers the
message, and the run starts again from zero. The task then looks stuck again. The loop is caused
by the missing signal, not by the restart.

WHICH PATTERN, per ARCHITECTURE_PATTERNS.md section 5: this is the OBSERVABILITY half that the
honesty clause requires of an existing resilience pattern. ``task_acks_late`` +
``task_reject_on_worker_lost`` is retry-on-worker-loss, and it emitted nothing — the clause names
that case "worse than none", because it turns a loud failure into a silent degradation. The
anti-fit for adding a pattern (over-abstraction, indirection with no variation) does not apply:
there is exactly one mechanism here, no interface, and its only alternative was a second wrong
diagnosis every time a long cert runs.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from celery.exceptions import BackendError

from src.infrastructure.cache.redis_best_effort import REDIS_CACHE_WRITE_FAULTS
from src.shared.utils.datetime_utils import parse_datetime_utc, utc_now
from src.shared.utils.json_rows import json_object
from src.shared.utils.scheduling import run_every
from src.workers.worker_code_revision import boot_code_revision

logger = logging.getLogger(__name__)

#: How often a running task republishes its liveness.
#:
#: 30s is chosen against the READER, not the writer: the question "is this task alive" is asked by
#: a human watching an admin poll, so the answer has to move on a human timescale. The write is one
#: small Redis set per beat, which is nothing beside a cert that burns a CPU for the better part of
#: an hour.
TASK_HEARTBEAT_INTERVAL_SECONDS: Final[float] = 30.0

#: How old a beat must be before the task is reported STALE.
#:
#: DERIVED from the interval rather than typed, so the two can never drift apart. Four intervals
#: tolerates a worker that is briefly starved of the GIL or blocked on a slow backend write
#: without crying wolf; a window at or below one interval would flag every healthy task, which is
#: what the canary test pins.
TASK_HEARTBEAT_STALE_AFTER_SECONDS: Final[float] = TASK_HEARTBEAT_INTERVAL_SECONDS * 4

#: Meta keys written into the result backend. Named once because the writer and the reader are in
#: different packages, and a key typed twice is how a reader silently stops finding the value.
HEARTBEAT_AT_KEY: Final[str] = "heartbeat_at"
HEARTBEAT_PID_KEY: Final[str] = "heartbeat_pid"
HEARTBEAT_STARTED_AT_KEY: Final[str] = "started_at"
#: The git commit this WORKER PROCESS booted with (`worker_code_revision.boot_code_revision`),
#: stamped into every beat so a poller can tell a worker that has not restarted since a commit
#: landed apart from one that has -- the STALEWORKER-1 failure this key exists to make visible.
HEARTBEAT_CODE_REVISION_KEY: Final[str] = "code_revision"

#: The state a beat is published under. Celery's own in-progress state, deliberately NOT a custom
#: one: a custom state would make ``AsyncResult.ready()`` behave the same but would break every
#: existing caller that compares against STARTED.
HEARTBEAT_STATE: Final[str] = "STARTED"

#: What one beat's write can raise: the result backend's Redis or socket failing, or a meta it cannot serialize
#: (REDIS_CACHE_WRITE_FAULTS), an empty task id (ValueError -- the thread-local case `_task_id_of` documents), and
#: Celery's own backend wrapper (BackendError).
BEAT_WRITE_FAULTS: Final[tuple[type[BaseException], ...]] = (*REDIS_CACHE_WRITE_FAULTS, ValueError, BackendError)

__all__ = [
    "HEARTBEAT_AT_KEY",
    "HEARTBEAT_CODE_REVISION_KEY",
    "HEARTBEAT_PID_KEY",
    "HEARTBEAT_STARTED_AT_KEY",
    "HEARTBEAT_STATE",
    "TASK_HEARTBEAT_INTERVAL_SECONDS",
    "TASK_HEARTBEAT_STALE_AFTER_SECONDS",
    "HeartbeatReading",
    "heartbeat_meta",
    "read_heartbeat",
    "task_heartbeat",
]


@dataclass(frozen=True)
class HeartbeatReading:
    """What a poller can honestly say about a task's liveness.

    ``stale`` is deliberately THREE-valued. ``False`` means a recent beat was seen, ``True`` means
    the beats stopped, and ``None`` means this task never published one — a task enqueued before
    the heartbeat shipped, or one still pending. Collapsing ``None`` into either of the others
    invents a fact: calling it stale reports a death that was never observed, and calling it fresh
    reports a life that was never observed. That collapse is the exact failure this module exists
    to fix, so it must not be reintroduced in the reading.
    """

    heartbeat_at: str | None = None
    age_seconds: float | None = None
    stale: bool | None = None
    #: The WORKER's boot-time git commit, read straight off the beat. None wherever `heartbeat_at`
    #: is: a task with no beat (never started, or already finished) carries no worker identity.
    code_revision: str | None = None


def heartbeat_meta(*, started_at: datetime, now: datetime, pid: int, code_revision: str | None = None) -> dict[str, object]:
    """Build the result-backend meta for one beat."""
    return {
        HEARTBEAT_AT_KEY: now.isoformat(),
        HEARTBEAT_STARTED_AT_KEY: started_at.isoformat(),
        HEARTBEAT_PID_KEY: pid,
        HEARTBEAT_CODE_REVISION_KEY: code_revision,
    }


def read_heartbeat(meta: object, *, now: datetime | None = None) -> HeartbeatReading:
    """Derive a liveness reading from whatever the result backend holds.

    ``meta`` is deliberately typed ``object``: the backend hands back a dict for a task that
    published meta, ``None`` for one that never did, and a plain string for a task that RAISED
    (the traceback). All three reach this function, and none of them may raise here — a poll that
    500s tells the operator even less than a stale STARTED did.
    """
    beat = json_object(meta)  # the backend's meta: a dict, or None / a traceback string (no beat)
    if beat is None:
        return HeartbeatReading()
    raw = beat.get(HEARTBEAT_AT_KEY)
    if not isinstance(raw, str):
        return HeartbeatReading()
    try:
        beat_at = parse_datetime_utc(raw)
    except ValueError, TypeError:
        # A malformed stamp is a bug in the WRITER, and the honest reading of it is "unknown".
        # Reporting stale here would turn a formatting defect into a false death report.
        logger.warning("unparseable task heartbeat timestamp: %r", raw)
        return HeartbeatReading()
    age = ((now or utc_now()) - beat_at).total_seconds()
    code_revision_raw = beat.get(HEARTBEAT_CODE_REVISION_KEY)
    return HeartbeatReading(
        heartbeat_at=raw,
        age_seconds=age,
        stale=age > TASK_HEARTBEAT_STALE_AFTER_SECONDS,
        code_revision=code_revision_raw if isinstance(code_revision_raw, str) else None,
    )


def _task_id_of(task: Any) -> str | None:
    """The running task's id, read in the TASK'S OWN THREAD.

    Celery's ``task.request`` is thread-local. Read from the heartbeat thread it is empty, and
    ``update_state`` then raises ``ValueError: task_id must not be empty. Got None instead.``
    MEASURED 2026-09-21 on a live cert: the first beat (task thread) landed, every periodic beat
    (heartbeat thread) failed, and ``heartbeat_at`` froze while the age climbed toward a FALSE
    stale report on a task that was running fine.
    """
    request = getattr(task, "request", None)
    task_id = getattr(request, "id", None)
    return str(task_id) if task_id else None


def _publish(task: Any, *, task_id: str | None, started_at: datetime, pid: int, code_revision: str | None) -> None:
    """Publish one beat, never letting a backend failure reach the task.

    This is telemetry running BESIDE real work, so a failure of the WRITE must be strictly less severe than the work
    failing: a cert that dies after 50 minutes because Redis hiccuped while reporting that the cert was alive would be a
    self-inflicted outage caused by the monitoring. The catch is the write's failure domain (BEAT_WRITE_FAULTS), not
    `Exception` (GATE-IDIOMS touched this file, 2026-11-07): a bug in our own code now surfaces with its traceback
    instead of reading as a backend hiccup and leaving every beat silently unpublished -- a false STALE report.
    """
    try:
        # `task_id` is passed EXPLICITLY: it was captured in the task's thread, because the
        # thread-local `task.request` this would otherwise fall back to is empty here.
        task.update_state(
            task_id=task_id,
            state=HEARTBEAT_STATE,
            meta=heartbeat_meta(started_at=started_at, now=utc_now(), pid=pid, code_revision=code_revision),
        )
    except BEAT_WRITE_FAULTS:  # telemetry must never outrank the work it observes
        logger.warning("task heartbeat could not be published", exc_info=True)


@contextlib.contextmanager
def task_heartbeat(
    task: Any,
    *,
    interval_seconds: float = TASK_HEARTBEAT_INTERVAL_SECONDS,
) -> Iterator[None]:
    """Publish a liveness beat for the duration of the wrapped work.

    Beats IMMEDIATELY on entry, then every ``interval_seconds`` until the block exits. The first
    beat is not an optimisation: a task killed inside its first interval is precisely the case an
    operator most wants to distinguish, and waiting one interval would leave it looking identical
    to the bare STARTED this module replaces.

    The thread is a daemon and is joined on exit, so it can neither outlive the worker nor leak
    from task to task.
    """
    started_at = utc_now()
    pid = os.getpid()
    stop = threading.Event()
    # Captured HERE, in the task's thread -- see `_task_id_of` for the measured failure.
    task_id = _task_id_of(task)
    # `lru_cache`d: this call costs a subprocess/env lookup only on the FIRST task any given
    # worker process runs, never per task -- see worker_code_revision.boot_code_revision.
    code_revision = boot_code_revision()

    _publish(task, task_id=task_id, started_at=started_at, pid=pid, code_revision=code_revision)

    def _beat() -> None:
        _publish(task, task_id=task_id, started_at=started_at, pid=pid, code_revision=code_revision)

    # shared.utils.scheduling.run_every: Event.wait returns True the moment stop is set, so shutdown is immediate rather
    # than waiting out the rest of an interval. This loop was the schedule idiom's source; it now lives there (GATE-IDIOMS).
    thread = threading.Thread(target=run_every, args=(_beat, interval_seconds, stop), name="pulsai-task-heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        # Bounded join: the thread only ever waits on the event, so it returns at once. The bound
        # exists so a pathological thread state can never hang the worker on task completion.
        with contextlib.suppress(RuntimeError):
            thread.join(timeout=interval_seconds + 1.0)
