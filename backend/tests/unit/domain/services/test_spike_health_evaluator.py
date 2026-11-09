"""Unit tests for the pure spike-health evaluator (T1-5).

Behavior-focused: given the shared compact-view shape
(``{primary_window, by_label}``), the evaluator must report the worst
status across all sources/labels, ignore empty (`unknown`) and thin
(`count < min_samples`) windows, and surface the offending entries.
"""

from __future__ import annotations

from typing import Any

from src.domain.services.spike_health_evaluator import (
    SpikeHealthOffender,
    SpikeHealthVerdict,
    evaluate_spike_health,
)
from src.shared.constants.spike_alert import (
    COMPACT_STATUS_CRITICAL,
    COMPACT_STATUS_OK,
    COMPACT_STATUS_UNKNOWN,
    COMPACT_STATUS_WARN,
)


def _entry(*, count: int, p95: float | None, status: str) -> dict[str, Any]:
    return {"count": count, "p50": p95, "p95": p95, "p99": p95, "status": status}


def _view(primary: str, labels: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"windows": [primary], "primary_window": primary, "by_label": {primary: labels}}


def test_all_ok_returns_ok_no_offenders() -> None:
    views = {
        "endpoint": _view("1m", {"/api": _entry(count=100, p95=0.05, status=COMPACT_STATUS_OK)}),
        "db": _view("1m", {"SELECT": _entry(count=100, p95=0.01, status=COMPACT_STATUS_OK)}),
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert isinstance(verdict, SpikeHealthVerdict)
    assert verdict.status == COMPACT_STATUS_OK
    assert verdict.offenders == ()


def test_worst_status_wins_and_offenders_collected() -> None:
    views = {
        "endpoint": _view(
            "1m",
            {
                "/api": _entry(count=100, p95=0.9, status=COMPACT_STATUS_WARN),
                "/login": _entry(count=80, p95=2.0, status=COMPACT_STATUS_CRITICAL),
            },
        ),
        "db": _view("1m", {"SELECT": _entry(count=100, p95=0.01, status=COMPACT_STATUS_OK)}),
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert verdict.status == COMPACT_STATUS_CRITICAL
    # Offenders sorted worst-first; only warn/critical entries included.
    # `sample_count` is part of the offender since 2026-09-06: a p95 cannot be judged without the
    # count behind it (20 samples means a burst just cleared min_samples, 2000 means real load).
    # Asserted here rather than dropped from the comparison, so this test keeps pinning the WHOLE
    # offender and would catch the field silently going missing again.
    assert verdict.offenders[0] == SpikeHealthOffender(
        source="endpoint", window="1m", label="/login", status=COMPACT_STATUS_CRITICAL, p95=2.0, sample_count=80
    )
    assert {o.label for o in verdict.offenders} == {"/login", "/api"}


def test_unknown_windows_are_ignored() -> None:
    views = {
        "endpoint": _view("1m", {"/api": _entry(count=0, p95=None, status=COMPACT_STATUS_UNKNOWN)}),
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert verdict.status == COMPACT_STATUS_OK
    assert verdict.offenders == ()


def test_thin_windows_below_min_samples_do_not_alert() -> None:
    views = {
        "endpoint": _view("1m", {"/api": _entry(count=5, p95=3.0, status=COMPACT_STATUS_CRITICAL)}),
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert verdict.status == COMPACT_STATUS_OK
    assert verdict.offenders == ()


def test_empty_views_returns_ok() -> None:
    assert evaluate_spike_health({}, min_samples=20).status == COMPACT_STATUS_OK


def test_missing_primary_window_block_is_tolerated() -> None:
    # Defensive: a malformed view (primary_window not present in by_label).
    bad = {"windows": ["1m"], "primary_window": "1m", "by_label": {}}
    verdict = evaluate_spike_health({"endpoint": bad}, min_samples=20)
    assert verdict.status == COMPACT_STATUS_OK


# ---------------------------------------------------------------------------
# 2026-09-05 — the CAUSE must outrank the VICTIMS.
#
# Every prod page so far led with a dependency. Measured from `spike_health_events`: on
# 2026-08-26 18:39:14 UTC five independent sources reported 6.150-6.627 s within 8% of each
# other. Five subsystems do not degrade to within 8% independently -- that is ONE stall, seen
# through whatever happened to be awaiting. The loop is the only source that can say so, and it
# is useless if the ranking buries it or the offender cap drops it.
# ---------------------------------------------------------------------------

#: Straight from the row the owner pasted: spike_health_events @ 2026-09-03 18:18:17+00.
PROD_CHART_INDICATORS_P95 = 2.265

#: The block measured in the production container the same day.
PROD_LOOP_STALL_SECONDS = 9.2419


def _loop_entry(*, count: int, p95: float, worst: float, status: str) -> dict[str, Any]:
    """A compact entry from the event-loop view, which also reports its worst sample."""
    return {**_entry(count=count, p95=p95, status=status), "max": worst}


def test_a_stalled_loop_outranks_the_endpoint_it_froze() -> None:
    """The loop must be offender #0 even though its p95 is three orders of magnitude smaller.

    A freeze is one sample among hundreds, so p95 ranks it last. Ranking on the number that
    actually drove the status puts the cause in the top line, where an operator reads it.
    """
    views = {
        "endpoint": _view(
            "5m",
            {"/api/v1/market/chart-indicators": _entry(count=200, p95=PROD_CHART_INDICATORS_P95, status=COMPACT_STATUS_CRITICAL)},
        ),
        "event_loop": _view(
            "2m",
            {
                "LAG": _loop_entry(
                    count=240,
                    p95=0.0004,
                    worst=PROD_LOOP_STALL_SECONDS,
                    status=COMPACT_STATUS_CRITICAL,
                )
            },
        ),
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert verdict.status == COMPACT_STATUS_CRITICAL
    assert verdict.offenders[0].source == "event_loop"
    assert verdict.offenders[0].worst == PROD_LOOP_STALL_SECONDS


def test_a_source_that_reports_no_worst_sample_still_ranks_by_p95() -> None:
    """DB / Redis / endpoint views carry no `max`; their ordering must not change."""
    views = {
        "endpoint": _view(
            "5m",
            {
                "slow": _entry(count=200, p95=2.0, status=COMPACT_STATUS_CRITICAL),
                "slower": _entry(count=200, p95=3.0, status=COMPACT_STATUS_CRITICAL),
            },
        )
    }

    offenders = evaluate_spike_health(views, min_samples=20).offenders

    assert [o.label for o in offenders] == ["slower", "slow"]
    assert all(o.worst is None for o in offenders)


def test_a_healthy_loop_is_not_an_offender() -> None:
    """The loop is a source like any other: `ok` must never reach the page."""
    views = {
        "event_loop": _view(
            "2m",
            {"LAG": _loop_entry(count=240, p95=0.0004, worst=0.02, status=COMPACT_STATUS_OK)},
        )
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert verdict.status == COMPACT_STATUS_OK
    assert verdict.offenders == ()


def test_a_thin_loop_window_after_boot_does_not_page() -> None:
    """The ring buffer fills over two minutes; a half-empty one must not alert on its own."""
    views = {
        "event_loop": _view(
            "2m",
            {"LAG": _loop_entry(count=3, p95=9.0, worst=9.0, status=COMPACT_STATUS_CRITICAL)},
        )
    }

    assert evaluate_spike_health(views, min_samples=20).status == COMPACT_STATUS_OK


# ---------------------------------------------------------------------------
# 2026-09-06 — a dependency critical must PROVE the dependency is slow, or name the queueing.
#
# The bands time the whole `await`, and for Redis that await contains a connection-pool
# acquisition and a suspension point. So the number is service time PLUS our own queueing, and
# the page has twice named a dependency that was healthy:
#
#   2026-08-07  paged `redis GET p95=0.425s`; Redis measured 5.47 ms minutes later
#   2026-09-06  paged `redis EXISTS p95=0.227s`; the same container measured EXISTS at 8.33 ms
#
# WHY THE PREVIOUS INVESTIGATION CLEARED THE LOOP AND WAS WRONG. It compared the dependency's
# p95 against the loop's p95 ("the loop-lag sampler read only 2ms in that tick, so lag alone
# does not explain it") and the two are not comparable populations:
#
#   redis EXISTS p95  -> 77 samples, essentially all inside a ~1 s dashboard burst
#   event_loop  p95   -> 240 samples at 0.5 s spacing = a 120-SECOND window, nearly all idle
#
# A one-second stall is ~2 of 240 loop samples, so it cannot move that p95 by construction. The
# comparable statistic is the loop's WORST sample in the window, and against that the numbers
# line up exactly. Reproduced locally 2026-09-06 with one dashboard load, both figures read from
# the same `/admin/health/observability` payload:
#
#   redis EXISTS  n=77  p95 0.173s  CRITICAL      (Redis on the same machine; EXISTS is ~50us)
#   event_loop    status ok  p50 0.001s  p95 0.002s  max 0.219s
#
# THE RULE, which needs no invented ratio: an await spanning a loop stall of L measures at least
# L. So when the loop's worst sample is >= the dependency's p95, that p95 is fully explicable
# WITHOUT the dependency being slow at all, and the page must say so. When it is smaller, the
# dependency took longer than the loop can account for and the dependency is named as before.
#
# Attribution NEVER suppresses. A stalled loop is a real incident; the page still fires, it just
# stops blaming the wrong subsystem.
# ---------------------------------------------------------------------------

#: The local reproduction above, which is also the shape of both production false causes.
REPRO_REDIS_EXISTS_P95 = 0.173
REPRO_LOOP_WORST_SECONDS = 0.219
REPRO_LOOP_P95_SECONDS = 0.002


def _burst_views(*, redis_p95: float, loop_worst: float, loop_p95: float = REPRO_LOOP_P95_SECONDS) -> dict[str, Any]:
    """A dependency critical beside the loop reading it saw, in one snapshot."""
    return {
        "redis": _view("5m", {"EXISTS": _entry(count=77, p95=redis_p95, status=COMPACT_STATUS_CRITICAL)}),
        "event_loop": _view(
            "2m",
            {"LAG": _loop_entry(count=240, p95=loop_p95, worst=loop_worst, status=COMPACT_STATUS_OK)},
        ),
    }


def _offender(verdict: SpikeHealthVerdict, source: str) -> SpikeHealthOffender:
    return next(off for off in verdict.offenders if off.source == source)


def test_a_loop_stall_larger_than_the_dependency_p95_is_named_as_the_cause() -> None:
    """The measured repro: 0.219 s of stall fully explains a 0.173 s Redis p95."""
    verdict = evaluate_spike_health(
        _burst_views(redis_p95=REPRO_REDIS_EXISTS_P95, loop_worst=REPRO_LOOP_WORST_SECONDS),
        min_samples=20,
    )

    assert _offender(verdict, "redis").explained_by_loop_stall_seconds == REPRO_LOOP_WORST_SECONDS


def test_attribution_uses_the_loops_worst_sample_not_its_percentile() -> None:
    """Guards the exact inference that cleared the loop twice.

    The loop p95 here is 0.002 s — two orders of magnitude below the Redis p95 — and an
    implementation comparing percentiles would find nothing to attribute. Only the worst sample
    is on a comparable footing with a burst-weighted dependency p95.
    """
    views = _burst_views(redis_p95=REPRO_REDIS_EXISTS_P95, loop_worst=REPRO_LOOP_WORST_SECONDS)
    assert views["event_loop"]["by_label"]["2m"]["LAG"]["p95"] < REPRO_REDIS_EXISTS_P95

    verdict = evaluate_spike_health(views, min_samples=20)

    assert _offender(verdict, "redis").explained_by_loop_stall_seconds is not None


def test_a_genuinely_slow_dependency_is_still_blamed_on_the_dependency() -> None:
    """The half that must not regress: a healthy loop leaves the dependency named."""
    verdict = evaluate_spike_health(
        _burst_views(redis_p95=0.500, loop_worst=0.004, loop_p95=0.001),
        min_samples=20,
    )

    assert _offender(verdict, "redis").explained_by_loop_stall_seconds is None


def test_attribution_does_not_suppress_the_page() -> None:
    """Naming the cause is the fix; silencing the alert would be a different, worse bug."""
    verdict = evaluate_spike_health(
        _burst_views(redis_p95=REPRO_REDIS_EXISTS_P95, loop_worst=REPRO_LOOP_WORST_SECONDS),
        min_samples=20,
    )

    assert verdict.status == COMPACT_STATUS_CRITICAL
    assert any(off.source == "redis" for off in verdict.offenders)


def test_the_loop_is_never_attributed_to_itself() -> None:
    """A stalled loop IS the cause; explaining it by itself would be circular."""
    views = {
        "event_loop": _view(
            "2m",
            {"LAG": _loop_entry(count=240, p95=0.5, worst=9.0, status=COMPACT_STATUS_CRITICAL)},
        )
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert _offender(verdict, "event_loop").explained_by_loop_stall_seconds is None


def test_no_loop_samples_claims_neither_cause() -> None:
    """With the loop unmeasured, "not the loop" is a guess. Report nothing, not innocence."""
    views = {
        "redis": _view("5m", {"EXISTS": _entry(count=77, p95=0.400, status=COMPACT_STATUS_CRITICAL)}),
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert _offender(verdict, "redis").explained_by_loop_stall_seconds is None


def test_every_victim_of_one_stall_is_attributed_not_just_the_first() -> None:
    """2026-08-26: five sources within 8% of each other — one stall, seen five ways."""
    views = {
        "redis": _view("5m", {"EXISTS": _entry(count=77, p95=0.173, status=COMPACT_STATUS_CRITICAL)}),
        "db": _view("5m", {"SELECT": _entry(count=27, p95=0.180, status=COMPACT_STATUS_CRITICAL)}),
        "endpoint": _view("5m", {"OTHER": _entry(count=43, p95=0.200, status=COMPACT_STATUS_CRITICAL)}),
        "event_loop": _view(
            "2m",
            {"LAG": _loop_entry(count=240, p95=0.002, worst=0.219, status=COMPACT_STATUS_OK)},
        ),
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    for source in ("redis", "db", "endpoint"):
        assert _offender(verdict, source).explained_by_loop_stall_seconds == 0.219, source


def test_a_boolean_worst_sample_is_not_read_as_one_second_of_stall() -> None:
    """``bool`` is a subclass of ``int``, so a naive isinstance check attributes everything.

    Caught auditing my own change rather than by a failure: ``isinstance(True, int)`` is True, so
    a JSON ``true`` in ``max`` would have become 1.0 seconds -- larger than most dependency p95s,
    and therefore an explanation for all of them at once.
    """
    views = {
        "redis": _view("5m", {"EXISTS": _entry(count=77, p95=0.173, status=COMPACT_STATUS_CRITICAL)}),
        "event_loop": _view("2m", {"LAG": _loop_entry(count=240, p95=0.002, worst=True, status=COMPACT_STATUS_OK)}),
    }

    verdict = evaluate_spike_health(views, min_samples=20)

    assert _offender(verdict, "redis").explained_by_loop_stall_seconds is None
