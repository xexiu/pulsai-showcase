"""Schedule: run a piece of work every interval until a stop event is set; the one home of the idiom.

IMPORTERS/CALLERS: workers/task_heartbeat (the beat thread -- this loop was its _beat, moved here); scripts/concept_owners.json
names this module the home of ``schedule-loop`` (src/lib/quality_gates/control_flow_idioms), so the one-definition
doors refuse a new hand-written periodic loop elsewhere and charge a touched file for its own;
tests/unit/shared/utils/test_scheduling.py. AFFECTED API: new module. DATA SCHEMAS: none.

WHY (GATE-IDIOMS, 2026-11-07): `concept_definitions --idioms` measured 10 hand-written schedule loops -- the API's
lifespan watches, the event-loop samplers, workers' task_heartbeat, the engine's loop, oil's hourly refresh -- each its
own. The shape is task_heartbeat's: ``Event.wait(interval)`` both sleeps and answers "stopped?", so a stop is seen at
once rather than after the rest of an interval. A caller that wants a run straight away calls its work first (as
task_heartbeat publishes on entry). The async form joins this module with its first async caller (the lifespan loops),
one home with both forms.

REUSE-AUDIT: considered workers/task_heartbeat._beat (this exact loop, a closure inside a context manager -- not
importable, so it MOVED here and task_heartbeat runs it), research/engine/runtime/engine_loop.Engine.run (the engine's
own minute clock, waking at bar closes -- a due time, not an interval; it moves here only if its timing test holds),
shared/utils/polling.poll_until_answer (ends on an answer -- a poll) and APScheduler / Celery beat (process-level
schedulers, not an in-process loop).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import threading
    from collections.abc import Callable


def run_every(work: Callable[[], object], interval_s: float, stop: threading.Event) -> None:
    """Run ``work`` each time ``interval_s`` seconds pass, until ``stop`` is set (seen at once, never an interval late)."""
    while not stop.wait(interval_s):
        work()


def run_then_wait(work: Callable[[], object], wait_s: Callable[[], float], stop: threading.Event) -> None:
    """Run ``work`` at once, then again after each wait ``wait_s()`` gives -- computed after each run, a due time such as
    the live engine's next bar close plus its grace (engine_loop.Engine.run, moved here 2026-11-08 with its timing test:
    a 0.01 s wait on the Event is kept as time.sleep kept it) -- until ``stop`` is set, seen at once."""
    work()
    while not stop.wait(wait_s()):
        work()
