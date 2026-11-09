"""A stored p95 that cannot be judged is a record that answers nothing.

THE QUESTION THIS EXISTS TO ANSWER (owner, 2026-09-06): was a "spike health CRITICAL" page
real, or an artefact? The number that decides it is the SAMPLE COUNT, because a percentile
over a handful of requests is not a percentile:

    organic traffic on the chart routes ...... 1-2 per 5-minute window (measured on prod)
    DEFAULT_SPIKE_ALERT_MIN_SAMPLES .......... 20

The floor already discards windows below 20 -- that part worked. What was missing is what
happens ABOVE it: 20 samples means a burst just cleared the bar, 2000 means genuine load, and
`spike_health_events` recorded neither. The count was computed on every tick, compared against
`min_samples`, and then dropped on the floor.

So the diagnosis had to be rebuilt from process timing instead (8 of 8 pages fell inside a
window the agent's sweep was running; 18 unprobed hours had no degraded tick at all). That
reasoning is sound but circumstantial, and it would have been one SELECT if the count had been
kept.

REUSE-AUDIT: `worst` already exists on this dataclass for the same shape of reason -- a stall's
p95 is ~0 while its worst sample IS the incident, so ranking on p95 alone buried the cause.
Extended that pattern rather than inventing a parallel one; `sample_count` is likewise a number
the evaluator already holds and used to discard.
"""

from __future__ import annotations

from typing import Any

from src.domain.services.spike_health_evaluator import SpikeHealthOffender, evaluate_spike_health
from src.shared.constants.spike_alert import COMPACT_STATUS_CRITICAL, COMPACT_STATUS_OK


def _view(label: str, *, count: int, p95: float, status: str) -> dict[str, Any]:
    return {
        "primary_window": "5m",
        "by_label": {"5m": {label: {"count": count, "p50": p95, "p95": p95, "p99": p95, "status": status}}},
    }


class TestTheCountSurvivesEvaluation:
    def test_an_offender_reports_the_window_sample_count(self) -> None:
        """THE REGRESSION: the count was used for the floor, then thrown away."""
        views = {"endpoint": _view("OTHER", count=63, p95=2.0, status=COMPACT_STATUS_CRITICAL)}

        verdict = evaluate_spike_health(views, min_samples=20)

        assert len(verdict.offenders) == 1
        assert verdict.offenders[0].sample_count == 63

    def test_a_burst_and_real_load_are_distinguishable(self) -> None:
        """The whole point: 20 and 2000 must not produce identical records."""
        burst = evaluate_spike_health(
            {"endpoint": _view("OTHER", count=20, p95=2.0, status=COMPACT_STATUS_CRITICAL)},
            min_samples=20,
        )
        real_load = evaluate_spike_health(
            {"endpoint": _view("OTHER", count=2000, p95=2.0, status=COMPACT_STATUS_CRITICAL)},
            min_samples=20,
        )

        assert burst.offenders[0].sample_count == 20
        assert real_load.offenders[0].sample_count == 2000
        assert burst.offenders[0].p95 == real_load.offenders[0].p95, "same p95 by construction -- the count is the ONLY thing telling them apart"

    def test_a_healthy_window_produces_no_offender_to_count(self) -> None:
        views = {"endpoint": _view("OTHER", count=500, p95=0.02, status=COMPACT_STATUS_OK)}

        assert evaluate_spike_health(views, min_samples=20).offenders == ()


class TestTheFieldIsOptional:
    """Sources that report no count must not be forced to invent one."""

    def test_it_defaults_to_none(self) -> None:
        offender = SpikeHealthOffender(
            source="endpoint",
            window="5m",
            label="OTHER",
            status=COMPACT_STATUS_CRITICAL,
            p95=1.0,
        )

        assert offender.sample_count is None

    def test_a_missing_count_key_yields_none_not_zero(self) -> None:
        """Zero is a CLAIM about the data; absent is the truth when nothing reported it.

        Reachable only with the floor disabled: `evaluate_spike_health` reads a missing count
        as 0, so any positive `min_samples` discards such an entry before it can become an
        offender. min_samples=0 is what a source reporting no counts would need.
        """
        views = {
            "custom": {
                "primary_window": "5m",
                "by_label": {"5m": {"THING": {"p95": 3.0, "status": COMPACT_STATUS_CRITICAL}}},
            }
        }

        verdict = evaluate_spike_health(views, min_samples=0)

        assert verdict.offenders[0].sample_count is None
