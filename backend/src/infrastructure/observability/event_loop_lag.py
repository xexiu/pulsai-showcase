"""Sample how late the event loop is running its own callbacks.

IMPORTERS / CALLERS: the FastAPI lifespan (start/stop), `GET /admin/health/observability`, and
the spike watcher's `gather_compact_views`.
AFFECTED API: adds the `event_loop` block to that endpoint's payload, and an `event_loop` source
to the spike-health verdict, the Telegram page and the `spike_health_events` table.
DATA SCHEMAS: none persisted here -- an in-process ring buffer, by design. Durability comes from
the spike-health history rows the watcher writes.
USER'S VERBATIM INSTRUCTION: "we also have admin ui routes that check what is slow, db, perf,
etc.. should be wired also there?"

WHY THIS METRIC AND NOT ANOTHER. The dashboard already shows endpoint p95, DB p95, Redis p95,
anomalies and spike-readiness. Each of those measures a VICTIM. When something blocks the loop,
all of them inflate at once and the page names whichever dependency happens to be sampled -- on
2026-08-07 that produced `spike health: CRITICAL — endpoint OTHER p95=12.091s, redis GET
p95=0.425s` while Redis, measured minutes later, was at 5.47 ms with no evictions. The dependency
was healthy. The loop was starved.

Loop lag names the CAUSE in one number; the other panels measure dependencies rather than the
loop itself.

MEASURED 2026-09-03, the defect this exists to catch: `list_models` ran 9,241.9 ms of blocking R2
I/O directly on the loop. For those 9.2 s every other in-flight request was frozen, and the only
visible symptom was every OTHER endpoint looking slow.

HOW IT WORKS. Ask the loop to wake us in `interval`, then measure how much longer it actually
took. A healthy loop overshoots by well under a millisecond; a blocked one overshoots by however
long the blocking call ran. That excess IS the lag, and it needs no instrumentation of the
handlers themselves -- which is the point, since the next blocking call will be somewhere nobody
thought to instrument.

TWO CORRECTIONS, 2026-09-05, after prod paged four more times while this meter read `ok`.

1. BACK-FILL. A stall swallows the wake-ups scheduled inside it: the sampler is asleep in the
   freeze along with everything else, so 9.24 s of block produced ONE sample where 18 half-second
   ticks were due. Dropping those biased every percentile optimistic at exactly the moment the
   loop was worst. Each swallowed tick WAS late -- by 8.74 s, 8.24 s, and so on down -- and is
   now recorded.

2. THE WORST SAMPLE IS A STATUS, NOT JUST A FIELD. Even back-filled, a 2 s freeze is four ticks
   in a 240-sample window, so p95 still reports a healthy loop -- correctly, because p95 answers
   "is the loop chronically late?" while an incident asks "did the loop stop?". Two questions,
   two bands; the badge is the worse of them.

The percentile and status helpers are the SAME ones the DB, Redis and endpoint panels use, so a
badge here means exactly what a badge there means -- including `unknown` for an empty window,
which is what keeps an unmeasured loop from reporting health it has not observed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from typing import Any

from src.infrastructure.observability._compact_view_helpers import (
    compute_percentiles,
    compute_threshold_status,
)
from src.shared.constants.observability_metrics import (
    EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS,
    EVENT_LOOP_LAG_LABEL,
    EVENT_LOOP_LAG_MAX_CRITICAL_SECONDS,
    EVENT_LOOP_LAG_MAX_WARN_SECONDS,
    EVENT_LOOP_LAG_P95_CRITICAL_SECONDS,
    EVENT_LOOP_LAG_P95_WARN_SECONDS,
    EVENT_LOOP_LAG_SAMPLE_INTERVAL_SECONDS,
    EVENT_LOOP_LAG_WINDOW_SAMPLES,
)
from src.shared.constants.spike_alert import worst_status

logger = logging.getLogger(__name__)

_SECONDS_PER_MINUTE = 60


class EventLoopLagSampler:
    """Rolling view of how far behind schedule the loop is waking up."""

    def __init__(
        self,
        interval_seconds: float = EVENT_LOOP_LAG_SAMPLE_INTERVAL_SECONDS,
        window_samples: int = EVENT_LOOP_LAG_WINDOW_SAMPLES,
    ) -> None:
        self._interval = interval_seconds
        self._samples: deque[float] = deque(maxlen=window_samples)
        # Timestamped, and longer-lived than `_samples`, so a stall can still EXPLAIN a
        # dependency percentile after it has stopped colouring the loop's own badge. Bounded by
        # the same arithmetic that sizes the ring buffer, so a pathological freeze cannot grow it.
        self._recent_stalls: deque[tuple[float, float]] = deque(
            maxlen=max(1, int(EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS / max(interval_seconds, 1e-9)))
        )
        self._task: asyncio.Task[None] | None = None
        #: Monotonic stamp of the last tick that actually ran. A WATCHDOG THREAD reads this to
        #: tell "the loop is idle" from "the loop is HELD", which this class alone cannot do: it
        #: is asleep inside the freeze along with everything else, so it learns a stall's LENGTH
        #: only after the stall ends, and never learns its CAUSE.
        #: None until the coroutine has ACTUALLY run once. Stamping `monotonic()` here instead
        #: measured the wrong thing: `_sampler` is a module-level singleton built at IMPORT, and
        #: the loop does not serve until every startup step has finished. The watchdog's first
        #: check therefore read the whole boot as one stall.
        #:
        #: MEASURED ON PROD 2026-09-07: `spike_watch_started` logged at 21:05:25.613, and 106 ms
        #: later `EVENT LOOP HELD for 22.557s`. A 22-second freeze cannot fit in 106 ms of
        #: wall-clock, so that reading is the container's boot time reported as a freeze -- on
        #: every deploy. The dump also attached whatever the main thread was in at that instant
        #: (`self._sslobj.read`), and I spent an hour treating that frame as a culprit.
        self._last_beat_monotonic: float | None = None

    def seconds_since_beat(self) -> float:
        """How long since the sampler's coroutine last got the loop. Safe to call off-thread.

        0.0 before the first beat: "how late is the loop running my callback" has no answer until
        it has run one, and 0.0 is the only answer that cannot invent a stall out of boot time.
        """
        if self._last_beat_monotonic is None:
            return 0.0
        return max(0.0, time.monotonic() - self._last_beat_monotonic)

    @property
    def window_seconds(self) -> float:
        """Wall-clock span the ring buffer covers while the loop is healthy."""
        return self._interval * (self._samples.maxlen or 0)

    def worst_since(self, seconds: float) -> float | None:
        """The worst stall observed in the last `seconds`, or None if nothing was measured.

        A LONGER memory than `snapshot()`, on purpose. The ring buffer above is sized for the
        loop's own badge -- "is the loop degraded now?" -- and its 2-minute span is a considered
        choice. This answers a different question, "did the loop stop recently enough to account
        for what that dependency is reporting?", and the dependency windows are 5 minutes.

        Measured on prod 2026-09-06: redis EXISTS held a byte-identical p95 across 23:29 and
        23:30 while its explanation went from 0.354 s to None, because the stall had aged out of
        the status window but not out of the 5-minute window its victims were judged on.

        Returns None rather than 0.0 for an unmeasured loop: a zero reads as "the loop was fine",
        which is a claim, and no samples support it.
        """
        if not self._recent_stalls:
            return None
        cutoff = time.monotonic() - max(0.0, seconds)
        recent = [lag for observed_at, lag in self._recent_stalls if observed_at >= cutoff]
        return max(recent) if recent else None

    def _record_lag(self, lag_seconds: float) -> None:
        """Record one observed lag plus the scheduled wake-ups that lag swallowed.

        A block does not merely make ONE tick late -- it consumes every tick due while it ran,
        and each of those was late by however much of the block remained. Recording only the
        tick that eventually fired under-counts the loop's unavailability by the length of the
        stall, which is the one moment the number matters.

        The back-fill is capped at the window size: a pathological freeze must not spin an
        unbounded append loop into a bounded deque.
        """
        lag = max(0.0, lag_seconds)
        self._samples.append(lag)
        # Only the observed sample is timestamped, never the back-filled ones below: those are
        # reconstructions of the SAME stall, and recording each would make one freeze look like
        # a burst of them to anything reading this deque.
        self._recent_stalls.append((time.monotonic(), lag))
        if self._interval <= 0:
            return
        capacity = self._samples.maxlen or 0
        swallowed = min(int(lag // self._interval), capacity)
        for tick in range(1, swallowed + 1):
            self._samples.append(lag - tick * self._interval)

    async def _run(self) -> None:
        while True:
            started = time.perf_counter()
            await asyncio.sleep(self._interval)
            self._last_beat_monotonic = time.monotonic()
            # Everything beyond the interval we asked for is time the loop was not free to run
            # this callback -- i.e. somebody else was holding it.
            self._record_lag(time.perf_counter() - started - self._interval)

    def start(self) -> None:
        """Begin sampling; a no-op when already running, or when called outside a running loop."""
        if self._task is not None and not self._task.done():
            return
        try:
            self._task = asyncio.get_running_loop().create_task(self._run())
        except RuntimeError:
            # Called from a synchronous context -- a Celery worker, a script, a module import
            # during collection. Those are legitimate callers, so this logs and returns.
            logger.debug("event-loop lag sampler idle: start() called outside a running loop")

    async def stop(self) -> None:
        """Cancel the sampler and await it, so lifespan teardown leaves no stray task."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def record_for_test(self, *lag_seconds: float) -> None:
        """Seed samples directly, so a test can assert the STATUS LADDER without sleeping.

        A test that waited for real lag would be slow and flaky; the ladder is the part with
        branches, and it is worth pinning exactly. Deliberately no back-fill: this seam lets a
        test control the window sample by sample.
        """
        self._samples.extend(lag_seconds)

    def record_stall_for_test(self, lag_seconds: float) -> None:
        """Seed ONE observed lag through the real back-fill path, without blocking a test."""
        self._record_lag(lag_seconds)

    def snapshot(self) -> dict[str, Any]:
        """Percentiles over the current window, with the status those thresholds imply."""
        percentiles = compute_percentiles(list(self._samples))
        worst = max(self._samples) if self._samples else None
        return {
            "status": worst_status(
                compute_threshold_status(
                    percentiles["p95"],
                    warn=EVENT_LOOP_LAG_P95_WARN_SECONDS,
                    critical=EVENT_LOOP_LAG_P95_CRITICAL_SECONDS,
                ),
                compute_threshold_status(
                    worst,
                    warn=EVENT_LOOP_LAG_MAX_WARN_SECONDS,
                    critical=EVENT_LOOP_LAG_MAX_CRITICAL_SECONDS,
                ),
            ),
            "samples": len(self._samples),
            **percentiles,
            "max": worst,
            # The worst stall still inside the span a DEPENDENCY is judged on, which is what
            # makes the tables below this card interpretable: any db/redis p95 under this number
            # may be a victim of the freeze rather than slow itself. `max` above cannot say that
            # -- it is scoped to the loop's own 2-minute badge window, and a stall ages out of it
            # three minutes before it stops inflating a 5-minute dependency percentile.
            #
            # Measured on prod 2026-09-06: redis EXISTS reported a byte-identical p95 at 23:29
            # and 23:30 while its explanation went 0.354s -> None, purely because of that gap.
            "attribution_max_seconds": self.worst_since(EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS),
            "attribution_window_seconds": EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS,
            # The LABEL as well as the seconds, because the number alone renders badly and the
            # formatting SoT is here, not in the browser. The admin card's `formatMilliseconds`
            # multiplies by 1000, so shipping only the seconds would have printed a 5-minute
            # window as "300000.0ms". `_window_label` is the same helper the compact view uses.
            "attribution_window_label": _window_label(EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS),
            "sample_interval_seconds": self._interval,
            "warn_threshold_seconds": EVENT_LOOP_LAG_P95_WARN_SECONDS,
            "critical_threshold_seconds": EVENT_LOOP_LAG_P95_CRITICAL_SECONDS,
            "max_warn_threshold_seconds": EVENT_LOOP_LAG_MAX_WARN_SECONDS,
            "max_critical_threshold_seconds": EVENT_LOOP_LAG_MAX_CRITICAL_SECONDS,
        }


_sampler = EventLoopLagSampler()


def get_event_loop_lag_sampler() -> EventLoopLagSampler:
    """The process-wide sampler. One loop per process, so one sampler."""
    return _sampler


def _window_label(seconds: float) -> str:
    """Render the ring buffer's span the way the other compact views label theirs ('5m').

    Derived from the sampler rather than written down, so resizing the buffer cannot leave a
    label advertising a window that no longer exists.
    """
    if seconds >= _SECONDS_PER_MINUTE:
        return f"{round(seconds / _SECONDS_PER_MINUTE)}m"
    return f"{round(seconds)}s"


def get_event_loop_compact_health_view(
    *,
    sampler: EventLoopLagSampler | None = None,
) -> dict[str, Any]:
    """Present the loop in the shared compact-view contract, beside DB / Redis / endpoints.

    WHY AN ADAPTER RATHER THAN A SECOND PAYLOAD SHAPE. `evaluate_spike_health` is a pure
    worst-of reduction over `{windows, primary_window, by_label}`. Teaching it to also
    understand the sampler's flat snapshot would put a per-source branch in the one function
    whose whole value is that it has none. Shaping the snapshot here instead is the Adapter row
    in ARCHITECTURE_PATTERNS, and its anti-fit ("our own modules already agree") does not apply:
    a ring-buffer snapshot and a windowed by-label view genuinely do not agree.

    The loop reports a single window because it HAS one -- the ring buffer. The other sources
    slice their observations into 5m/15m/60m; inventing those here would fabricate history the
    sampler never kept.
    """
    active = sampler if sampler is not None else get_event_loop_lag_sampler()
    snapshot = active.snapshot()
    window = _window_label(active.window_seconds)
    entry = {
        "count": snapshot["samples"],
        "p50": snapshot["p50"],
        "p95": snapshot["p95"],
        "p99": snapshot["p99"],
        "max": snapshot["max"],
        "status": snapshot["status"],
        # ATTRIBUTION EVIDENCE, and deliberately neither a second window nor a top-level key.
        #
        # A second window would become another by-label entry, which `evaluate_spike_health`
        # reduces over -- so it would surface as a new OFFENDER and change what pages, which is
        # not what a longer memory is for. A top-level key was the first attempt and two contract
        # tests correctly rejected it: the shared compact shape is exactly
        # {windows, primary_window, by_label}, and letting one source bolt fields onto it is the
        # per-source drift those tests exist to prevent.
        #
        # It belongs here, beside `max`, because it describes the same label's observations --
        # just over the span a DEPENDENCY is judged on (5m) rather than the span the loop's own
        # badge uses (2m). Consumers read entries by key, so an extra field is inert to every
        # reader that does not ask for it.
        "attribution_max_seconds": active.worst_since(EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS),
        "attribution_window_seconds": EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS,
    }
    return {
        "windows": [window],
        "primary_window": window,
        "by_label": {window: {EVENT_LOOP_LAG_LABEL: entry}},
    }


__all__ = [
    "EventLoopLagSampler",
    "get_event_loop_compact_health_view",
    "get_event_loop_lag_sampler",
]
