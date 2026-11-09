"""The loop-lag sampler must measure the loop, and must not claim health it has not observed.

IMPORTERS / CALLERS: none -- a pytest module.
AFFECTED API: none. Exercises the sampler directly.
DATA SCHEMAS: none.
USER'S VERBATIM INSTRUCTION: "we also have admin ui routes that check what is slow, db, perf,
etc.. should be wired also there?"

The status ladder is asserted with SEEDED samples rather than real waiting: a test that blocked
the loop for 250 ms to earn a `critical` badge would be slow and, under parallel test load,
flaky in the direction that matters least. The branches are what deserve pinning.

One test does exercise the real timing path, because a sampler that never actually observes the
loop would pass every seeded assertion while measuring nothing -- the same silent-success shape
this metric exists to expose.

2026-09-05 -- WHAT A REAL STALL LOOKS LIKE, and why the seeded ladder alone was not enough.
The ladder tests below seed N IDENTICAL samples, which models a loop that was continuously late
for the whole window. That is not the shape of the defect this sampler exists to catch. A 9.24 s
block produces exactly ONE late wake-up, because the sampler was asleep inside the block along
with everything else -- so `p95` over a 240-sample window discards it and the badge reads `ok`
during the incident. Both halves of the fix are pinned here: missed ticks are BACK-FILLED (the
loop really was late for each one, and not recording them biased every percentile optimistic),
and a single freeze is judged on the WORST sample, not only the 95th percentile.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from src.infrastructure.observability import event_loop_lag as lag_module
from src.infrastructure.observability.event_loop_lag import (
    EventLoopLagSampler,
    get_event_loop_compact_health_view,
)
from src.shared.constants.observability_metrics import (
    EVENT_LOOP_LAG_LABEL,
    EVENT_LOOP_LAG_MAX_CRITICAL_SECONDS,
    EVENT_LOOP_LAG_MAX_WARN_SECONDS,
    EVENT_LOOP_LAG_P95_CRITICAL_SECONDS,
    EVENT_LOOP_LAG_P95_WARN_SECONDS,
    EVENT_LOOP_LAG_WINDOW_SAMPLES,
)

#: A loop waking on schedule overshoots by a fraction of a millisecond.
HEALTHY_LAG_SECONDS = 0.0002

#: Measured in the production container on 2026-09-03: `list_models` held the loop this long.
PROD_STALL_SECONDS = 9.2419

#: Measured in prod on 2026-08-25, recorded in `spike_health_events` as `redis GET p95=2.099s`.
#: Redis was healthy; that number is the stall, observed through whatever was awaiting.
PROD_SHORTER_STALL_SECONDS = 2.099


def _window_with_one_stall(stall_seconds: float) -> EventLoopLagSampler:
    """A full window of healthy samples with a single freeze in it -- the real shape."""
    sampler = EventLoopLagSampler()
    sampler.record_for_test(*[HEALTHY_LAG_SECONDS] * (EVENT_LOOP_LAG_WINDOW_SAMPLES - 1))
    sampler.record_for_test(stall_seconds)
    return sampler


class TestAnUnmeasuredLoopReportsUnknown:
    def test_a_fresh_sampler_is_unknown_not_ok(self) -> None:
        """An empty window must not render as a healthy badge.

        This repo has repeatedly paid for the opposite: an unmeasured zero that reads as a
        measured flat. `unknown` is the honest answer before the first sample lands.
        """
        snapshot = EventLoopLagSampler().snapshot()
        assert snapshot["status"] == "unknown"
        assert snapshot["samples"] == 0
        assert snapshot["p95"] is None
        assert snapshot["max"] is None


class TestBootTimeIsNotAStall:
    """A sampler that has never run has no lag to report -- least of all the boot it slept through.

    MEASURED ON PROD 2026-09-07. `spike_watch_started` logged at 21:05:25.613, and 106 ms later
    the watchdog logged `EVENT LOOP HELD for 22.557s`. A 22-second freeze does not fit inside
    106 ms of wall-clock: `_sampler` is a module-level singleton built at IMPORT, its beat was
    stamped there, and the loop does not serve until every startup step finishes. The gap between
    those two moments is the container's boot, and it was reported as a freeze on every deploy.

    The cost was not just a wrong number. The dump attached whatever the main thread was in at
    that instant -- `self._sslobj.read` -- and I spent an hour treating that frame as a culprit.
    A false positive that arrives with a plausible stack is worse than a silent one.
    """

    def test_a_sampler_that_never_ran_reports_no_lag(self) -> None:
        assert EventLoopLagSampler().seconds_since_beat() == 0.0

    def test_boot_time_before_the_first_beat_is_not_reported(self, monkeypatch) -> None:
        """Import at t=0, loop starts serving 22.5s later -> still 0.0, not 22.5."""
        sampler = EventLoopLagSampler()
        monkeypatch.setattr(lag_module.time, "monotonic", lambda: time.monotonic() + 22.557)

        assert sampler.seconds_since_beat() == 0.0

    @pytest.mark.asyncio
    async def test_once_it_has_beaten_it_measures_normally(self) -> None:
        """The guard must not disable the metric -- after a real beat, lag is reported again."""
        sampler = EventLoopLagSampler(interval_seconds=0.01)
        sampler.start()
        await asyncio.sleep(0.05)
        try:
            assert sampler.seconds_since_beat() >= 0.0
            assert sampler._last_beat_monotonic is not None, "a running sampler must stamp a beat"
        finally:
            await sampler.stop()


class TestTheStatusLadder:
    def test_a_quiet_loop_is_ok(self) -> None:
        sampler = EventLoopLagSampler()
        sampler.record_for_test(*[0.0005] * 20)
        assert sampler.snapshot()["status"] == "ok"

    def test_lag_at_the_warn_threshold_is_warn(self) -> None:
        sampler = EventLoopLagSampler()
        sampler.record_for_test(*[EVENT_LOOP_LAG_P95_WARN_SECONDS] * 20)
        assert sampler.snapshot()["status"] == "warn"

    def test_lag_at_the_critical_threshold_is_critical(self) -> None:
        sampler = EventLoopLagSampler()
        sampler.record_for_test(*[EVENT_LOOP_LAG_P95_CRITICAL_SECONDS] * 20)
        assert sampler.snapshot()["status"] == "critical"

    def test_the_9_2_second_stall_that_prompted_this_is_critical(self) -> None:
        """The measured defect: `list_models` held the loop for 9,241.9 ms on 2026-09-03.

        Kept as written, but read it for what it asserts: a loop late by 9.24 s on EVERY one of
        20 samples. `TestOneFreezeInAHealthyWindow` covers the shape a single block really makes.
        """
        sampler = EventLoopLagSampler()
        sampler.record_for_test(*[PROD_STALL_SECONDS] * 20)
        snapshot = sampler.snapshot()
        assert snapshot["status"] == "critical"
        assert snapshot["max"] == pytest.approx(PROD_STALL_SECONDS)


class TestOneFreezeInAHealthyWindow:
    """A single block is the defect; p95 over a 240-sample window cannot see one sample."""

    def test_a_single_9_2_second_freeze_is_critical(self) -> None:
        """The regression: 239 healthy samples plus one 9.24 s freeze used to badge `ok`.

        p95 of that window is ~0.2 ms, so the percentile is not wrong -- it is answering
        "is the loop chronically late?" when the question during an incident is "did the loop
        stop?". Those need different statistics, and the second one is the max.
        """
        snapshot = _window_with_one_stall(PROD_STALL_SECONDS).snapshot()
        assert snapshot["max"] == pytest.approx(PROD_STALL_SECONDS)
        assert snapshot["status"] == "critical"

    def test_a_single_2_1_second_freeze_is_critical(self) -> None:
        """2.099 s froze every in-flight request; duty cycle does not soften that."""
        assert _window_with_one_stall(PROD_SHORTER_STALL_SECONDS).snapshot()["status"] == "critical"

    def test_a_freeze_at_the_max_warn_band_is_warn(self) -> None:
        assert _window_with_one_stall(EVENT_LOOP_LAG_MAX_WARN_SECONDS).snapshot()["status"] == "warn"

    def test_a_brief_hiccup_stays_ok(self) -> None:
        """The band must sit above ordinary scheduling noise or it pages on nothing.

        Healthy samples are sub-millisecond and the stalls that paged prod were 2.1-9.2 s, so
        the warn line sits in a wide empty gap. A single sample just under it must not alert.
        """
        below_warn = EVENT_LOOP_LAG_MAX_WARN_SECONDS / 2
        assert _window_with_one_stall(below_warn).snapshot()["status"] == "ok"

    def test_the_max_thresholds_are_published_in_the_snapshot(self) -> None:
        """The badge can now go critical on a tiny p95; the payload must say why."""
        snapshot = _window_with_one_stall(PROD_STALL_SECONDS).snapshot()
        assert snapshot["max_warn_threshold_seconds"] == EVENT_LOOP_LAG_MAX_WARN_SECONDS
        assert snapshot["max_critical_threshold_seconds"] == EVENT_LOOP_LAG_MAX_CRITICAL_SECONDS


class TestTheWindowIsBounded:
    def test_older_samples_fall_out(self) -> None:
        """A stall from long ago must stop colouring the badge once the window rolls past it."""
        sampler = EventLoopLagSampler(window_samples=5)
        sampler.record_for_test(9.0)
        sampler.record_for_test(*[0.0001] * 5)
        snapshot = sampler.snapshot()
        assert snapshot["samples"] == 5
        assert snapshot["status"] == "ok"


class TestMissedTicksAreBackFilled:
    """Not recording the wake-ups a stall ate biases every percentile optimistic.

    During a block the sampler is asleep with everything else, so one 9 s freeze yields one
    sample where 18 half-second ticks were due. Each of those ticks WAS late -- by 8.74 s,
    8.24 s, and so on -- and dropping them is the sampler under-reporting precisely when the
    loop is worst.
    """

    def test_one_long_block_records_more_than_one_late_sample(self) -> None:
        sampler = EventLoopLagSampler(interval_seconds=0.5)
        sampler.record_stall_for_test(9.2419)
        snapshot = sampler.snapshot()
        assert snapshot["samples"] > 1, "a 9.2 s block over a 0.5 s interval ate ~18 wake-ups"
        assert snapshot["max"] == pytest.approx(9.2419)

    def test_back_fill_is_bounded_by_the_window(self) -> None:
        """A very long block must not be able to blow the ring buffer's memory bound."""
        sampler = EventLoopLagSampler(interval_seconds=0.5, window_samples=10)
        sampler.record_stall_for_test(600.0)
        assert sampler.snapshot()["samples"] == 10

    def test_a_punctual_wake_up_records_exactly_one_sample(self) -> None:
        """Back-fill must not invent samples when nothing was missed."""
        sampler = EventLoopLagSampler(interval_seconds=0.5)
        sampler.record_stall_for_test(0.0004)
        assert sampler.snapshot()["samples"] == 1


class TestTheCompactHealthView:
    """The loop presents itself the way DB / Redis / endpoints do, so the spike watcher can
    reduce it with the SAME pure evaluator instead of learning a second payload shape."""

    def test_the_view_matches_the_shared_compact_contract(self) -> None:
        sampler = _window_with_one_stall(PROD_STALL_SECONDS)
        view = get_event_loop_compact_health_view(sampler=sampler)
        assert set(view) == {"windows", "primary_window", "by_label"}
        primary = view["primary_window"]
        assert primary in view["windows"]
        entry = view["by_label"][primary][EVENT_LOOP_LAG_LABEL]
        assert entry["status"] == "critical"
        assert entry["count"] == EVENT_LOOP_LAG_WINDOW_SAMPLES
        assert entry["max"] == pytest.approx(PROD_STALL_SECONDS)

    def test_an_unmeasured_loop_reports_unknown_not_ok(self) -> None:
        view = get_event_loop_compact_health_view(sampler=EventLoopLagSampler())
        entry = view["by_label"][view["primary_window"]][EVENT_LOOP_LAG_LABEL]
        assert entry["status"] == "unknown"
        assert entry["count"] == 0

    def test_the_window_label_is_derived_from_the_sampler(self) -> None:
        """A hand-written '2m' would drift the moment the ring buffer is resized."""
        sampler = EventLoopLagSampler(interval_seconds=0.5, window_samples=240)
        assert get_event_loop_compact_health_view(sampler=sampler)["primary_window"] == "2m"


class TestItActuallyObservesTheLoop:
    @pytest.mark.asyncio
    async def test_samples_accumulate_while_running(self) -> None:
        """Without this, every seeded assertion above could pass on a sampler that never runs."""
        sampler = EventLoopLagSampler(interval_seconds=0.01)
        sampler.start()
        try:
            await asyncio.sleep(0.1)
        finally:
            await sampler.stop()
        assert sampler.snapshot()["samples"] > 0

    @pytest.mark.asyncio
    async def test_a_real_block_is_seen_as_a_real_stall(self) -> None:
        """End to end on the live timing path: block the loop, expect the badge to say so.

        The seeded tests pin the ladder; this one proves the sampler actually attributes a
        genuine synchronous block to the loop rather than sleeping through it unrecorded.
        """
        sampler = EventLoopLagSampler(interval_seconds=0.01)
        sampler.start()
        try:
            await asyncio.sleep(0.05)
            # Blocking the loop is the ENTIRE point here -- this test asserts the sampler
            # attributes a genuine synchronous freeze rather than sleeping through it.
            time.sleep(EVENT_LOOP_LAG_MAX_CRITICAL_SECONDS + 0.2)  # noqa: ASYNC251
            await asyncio.sleep(0.05)
        finally:
            await sampler.stop()
        snapshot = sampler.snapshot()
        assert snapshot["max"] is not None
        assert snapshot["max"] >= EVENT_LOOP_LAG_MAX_CRITICAL_SECONDS
        assert snapshot["status"] == "critical"

    @pytest.mark.asyncio
    async def test_stop_leaves_no_running_task(self) -> None:
        """Lifespan teardown must not leak the sampler; the stray-task class is a known cost."""
        sampler = EventLoopLagSampler(interval_seconds=0.01)
        sampler.start()
        await asyncio.sleep(0.02)
        await sampler.stop()
        assert sampler._task is None

    def test_start_outside_a_running_loop_is_survivable(self) -> None:
        """Celery workers and scripts import this module; start() there must not raise."""
        sampler = EventLoopLagSampler()
        sampler.start()
        assert sampler.snapshot()["status"] == "unknown"
