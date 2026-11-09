"""run_every and run_then_wait: the one home of SCHEDULE (GATE-IDIOMS).

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.
"""

from __future__ import annotations

import threading
import time

from src.shared.utils.scheduling import run_every, run_then_wait


class _StopAfter(threading.Event):
    """An Event whose wait() returns True (stopped) once ``n`` intervals have passed, recording each interval -- no real
    time passes."""

    def __init__(self, n: int) -> None:
        super().__init__()
        self.waited: list[float | None] = []
        self._n = n

    def wait(self, timeout: float | None = None) -> bool:
        self.waited.append(timeout)
        return len(self.waited) > self._n


def test_the_work_runs_after_each_interval_until_the_stop() -> None:
    runs: list[int] = []
    stop = _StopAfter(3)

    run_every(lambda: runs.append(len(runs)), 60.0, stop)

    assert runs == [0, 1, 2]
    assert stop.waited == [60.0, 60.0, 60.0, 60.0]


def test_a_stop_before_the_first_interval_runs_nothing() -> None:
    runs: list[int] = []

    run_every(lambda: runs.append(1), 5.0, _StopAfter(0))

    assert runs == []


def test_a_due_time_schedule_runs_at_once_then_waits_what_the_caller_computes_after_each_run() -> None:
    """The live engine's loop (engine_loop.Engine.run): it steps at once, then waits until the next bar's close plus its
    grace -- a wait computed after each step (WAKE-LATE: 0.1 s just before a grace, POLL_S otherwise)."""
    runs: list[int] = []
    waits = iter([0.1, 2.0, 0.01, 0.5])
    stop = _StopAfter(3)

    run_then_wait(lambda: runs.append(len(runs)), lambda: next(waits), stop)

    assert runs == [0, 1, 2, 3]
    assert stop.waited == [0.1, 2.0, 0.01, 0.5]


def test_a_short_wait_on_a_real_event_is_as_short_as_asked() -> None:
    """BAR-FINAL's look at a just-closed minute every SETTLE_POLL_S (0.01 s): ten waits on a real Event take ~0.1 s, as
    time.sleep did in the engine's own loop -- the timing the move into this home must keep."""
    stop, runs = threading.Event(), []

    def work() -> None:
        runs.append(1)
        if len(runs) == 11:
            stop.set()

    started = time.monotonic()
    run_then_wait(work, lambda: 0.01, stop)
    elapsed = time.monotonic() - started

    assert len(runs) == 11
    assert 0.09 <= elapsed < 0.3
