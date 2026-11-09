"""The loop must remember a stall for as long as its victims do, or attribution goes blind.

REUSE-AUDIT: considered tests/unit/infrastructure/observability/test_event_loop_lag.py -- the
sampler's main suite, covering back-fill, the p95/max bands and the compact-view contract; not
extending because this pins a DIFFERENT retention with a different purpose (how long a stall stays
available to EXPLAIN another source, not how long it colours the loop's own badge), and mixing the
two in one file is what made the window length look like a single decision when it is two.
Considered tests/unit/domain/services/test_spike_health_evaluator.py -- pins that attribution is
computed from a snapshot; not extending because the defect here is that the snapshot stops
carrying the number, which is upstream of anything that file can see. Considered
tests/unit/architecture/test_async_routes_do_not_block_the_event_loop.py -- an architecture gate
on route definitions, unrelated to sampler retention.

MEASURED ON PROD, 2026-09-06, in `spike_health_events` -- three consecutive ticks, same window
contents, and the explanation evaporates halfway through:

    observed_at  source  label   p95_seconds         explained_by_loop_stall_seconds
    23:29:1x     redis   EXISTS  0.0691687276586890  0.354259068146348
    23:30:1x     redis   EXISTS  0.0691687276586890  None
    23:31:1x     redis   EXISTS  0.0691726209595799  None

Redis is at 69 ms in all three -- byte-identical p95 at 23:29 and 23:30, so the 5-minute window
still holds exactly the same samples. What changed is that the loop's OWN window is 2 minutes
(EVENT_LOOP_LAG_WINDOW_SAMPLES = 240 at a 0.5 s interval), so by 23:30 the stall had aged out of
the only place the evaluator could read it.

The dependency windows are 5 minutes. So for the last three minutes of every stall's blast radius
the victim looks unexplained -- and pages, naming Redis, which is the four days of misleading
alerts this whole thread is about.

WHY NOT SIMPLY LENGTHEN THE SAMPLER'S WINDOW. Its 2-minute span is a considered decision, recorded
on the constant: "long enough to survive one bad request without being so long that a stall from
ten minutes ago still shows." That reasoning is SOUND for the loop's own badge -- a stall should
stop colouring the loop critical once it is over. It is simply the wrong window for a different
question. The module already splits p95 from max because "p95 and max answer two different
questions and both are needed"; this is the third question, and it gets its own retention rather
than distorting either band.
"""

from __future__ import annotations

import pytest

from src.infrastructure.observability.event_loop_lag import (
    EventLoopLagSampler,
    get_event_loop_compact_health_view,
)
from src.shared.constants.observability_metrics import (
    EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS,
    EVENT_LOOP_LAG_LABEL,
    EVENT_LOOP_LAG_SAMPLE_INTERVAL_SECONDS,
    EVENT_LOOP_LAG_WINDOW_SAMPLES,
    OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES,
)

#: The stall from the prod row above.
PROD_STALL_SECONDS = 0.354259068146348
HEALTHY_LAG_SECONDS = 0.0004

SECONDS_PER_MINUTE = 60


class TestTheAttributionWindowCoversTheDependencyWindow:
    """The number that makes the two comparable, derived rather than typed twice."""

    def test_it_is_at_least_as_long_as_the_dependency_primary_window(self) -> None:
        """A shorter attribution memory is precisely the 23:30 blind spot."""
        primary_minutes = OBSERVABILITY_COMPACT_METRIC_WINDOWS_MINUTES[0][1]

        assert primary_minutes * SECONDS_PER_MINUTE <= EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS

    def test_it_is_longer_than_the_loop_status_window(self) -> None:
        """If these were equal the extra retention would not exist and this is a no-op change."""
        status_window = EVENT_LOOP_LAG_SAMPLE_INTERVAL_SECONDS * EVENT_LOOP_LAG_WINDOW_SAMPLES

        assert status_window < EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS


class TestTheSamplerRemembersLongerThanItReports:
    def test_a_stall_survives_the_status_window_rolling_over(self) -> None:
        """The exact 23:29 -> 23:30 transition: the badge forgets, the attribution must not."""
        sampler = EventLoopLagSampler()
        sampler.record_stall_for_test(PROD_STALL_SECONDS)

        # Push the stall out of the 240-sample status window entirely.
        sampler.record_for_test(*[HEALTHY_LAG_SECONDS] * (EVENT_LOOP_LAG_WINDOW_SAMPLES + 50))

        assert sampler.snapshot()["max"] == pytest.approx(HEALTHY_LAG_SECONDS), "precondition: the stall must have aged out of the status window"
        assert sampler.worst_since(EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS) == pytest.approx(PROD_STALL_SECONDS)

    def test_an_unmeasured_loop_claims_nothing(self) -> None:
        """No samples means no evidence -- never a zero, which would read as a healthy loop."""
        assert EventLoopLagSampler().worst_since(EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS) is None

    def test_a_stall_older_than_the_attribution_window_is_forgotten(self) -> None:
        """Unbounded memory would excuse a dependency for a stall long since over."""
        sampler = EventLoopLagSampler()
        sampler.record_stall_for_test(PROD_STALL_SECONDS)

        assert sampler.worst_since(0.0) is None


class TestTheCompactViewCarriesTheNumber:
    """The evaluator is pure, so the snapshot has to hand it the evidence."""

    def test_the_view_publishes_the_attribution_max(self) -> None:
        sampler = EventLoopLagSampler()
        sampler.record_stall_for_test(PROD_STALL_SECONDS)
        sampler.record_for_test(*[HEALTHY_LAG_SECONDS] * (EVENT_LOOP_LAG_WINDOW_SAMPLES + 50))

        view = get_event_loop_compact_health_view(sampler=sampler)
        entry = view["by_label"][view["primary_window"]][EVENT_LOOP_LAG_LABEL]

        assert entry["attribution_max_seconds"] == pytest.approx(PROD_STALL_SECONDS)
        assert entry["attribution_window_seconds"] == EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS

    def test_it_does_not_add_a_second_window_to_the_contract(self) -> None:
        """A new window would become a new OFFENDER row and change what pages. It must not."""
        sampler = EventLoopLagSampler()
        sampler.record_for_test(HEALTHY_LAG_SECONDS)

        view = get_event_loop_compact_health_view(sampler=sampler)

        assert len(view["windows"]) == 1
        assert set(view["by_label"]) == set(view["windows"])

    def test_the_admin_snapshot_carries_it_too(self) -> None:
        """The admin health card renders `snapshot()`, not the compact view.

        Owner, 2026-09-07: *"is that wited on the existing admin ui???"*. It was not. The card
        exists and already says high lag means the API is blocked rather than a dependency, but
        it had no number for HOW RECENTLY, so the tables under it stayed uninterpretable.

        This is the field that makes them interpretable: any db/redis p95 below it may be a
        victim of the freeze. `max` cannot serve -- it is the loop's own 2-minute badge window,
        which forgets a stall three minutes before that stall stops inflating a 5-minute
        dependency percentile.
        """
        sampler = EventLoopLagSampler()
        sampler.record_stall_for_test(PROD_STALL_SECONDS)
        sampler.record_for_test(*[HEALTHY_LAG_SECONDS] * (EVENT_LOOP_LAG_WINDOW_SAMPLES + 50))

        snapshot = sampler.snapshot()

        assert snapshot["max"] == pytest.approx(HEALTHY_LAG_SECONDS), "precondition: the badge window has forgotten the stall"
        assert snapshot["attribution_max_seconds"] == pytest.approx(PROD_STALL_SECONDS)
        assert snapshot["attribution_window_seconds"] == EVENT_LOOP_ATTRIBUTION_WINDOW_SECONDS
        # The LABEL travels too. The admin card's formatter multiplies seconds by 1000, so
        # shipping only the number printed a five-minute window as "300000.0ms". Formatting has
        # one owner -- here -- rather than a second copy in TypeScript that drifts.
        assert snapshot["attribution_window_label"] == "5m"

    def test_it_does_not_bolt_fields_onto_the_shared_top_level_shape(self) -> None:
        """The first attempt put these at the top level and two contract tests caught it.

        The shared compact shape is exactly {windows, primary_window, by_label}. Letting one
        source add keys there is the per-source drift those tests exist to prevent, so the
        evidence lives on the LAG entry instead -- beside `max`, which it is a longer-span
        sibling of.
        """
        view = get_event_loop_compact_health_view(sampler=EventLoopLagSampler())

        assert set(view) == {"windows", "primary_window", "by_label"}
