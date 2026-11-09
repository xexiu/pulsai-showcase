"""An IC too high to be a forward-PRICE IC cannot grade EDGE while the lane still says `ic`.

MEASURED 2026-08-21 across the hunt corpus: 92 books carry an `ic_suspect` field, 11 are
promoted, and **11 of 11 promoted books are `ic_suspect: True` with `gate_lane: "ic"`** -- every
promoted book in the corpus was graded over its own leak warning. All eleven are the VRP family
on 1d, and their metrics collapse into two signatures (six at `ic 0.547 / sr 2.63`, five at
`ic 0.500 / sr 2.63`), which is its own problem.

The warning the pipeline writes and then discards:

    |ic|=0.547 exceeds the forward-price rank-IC ceiling 0.3 -- either this IC is against a
    non-price target (declare gate_lane='book') or it leaks

`loop_contract._flag_emission_sanity` computes that, `research_verdict` never reads it, and
`ic > EDGE_IC_MIN` is then auto-passed by an IC measured against something else entirely. A
forward-price rank-IC in crypto lives at 0.02-0.07; 0.547 is an order of magnitude out.

WHAT THIS DELIBERATELY DOES NOT DO. `_flag_emission_sanity`'s docstring records the original
decision -- "Flagged, not silently re-laned: the emitter must declare its lane" -- and that
choice stands. Re-laning would hide a broken emitter. Declining to GRADE an undeclared suspect
IC is the same rule enforced rather than merely advertised: until the emitter declares
`gate_lane='book'`, the IC is not usable as evidence of edge, so the verdict caps at `scout`.
Declaring the lane restores the higher tier, which makes this fully reversible by the emitter.
"""

from __future__ import annotations

from src.domain.services.edge_lifecycle.gate import (
    GATE_LANE_BOOK,
    GATE_LANE_IC,
    PRICE_IC_CEILING,
    GateMetrics,
    select_research_verdict,
)

# The measured VRP shape: an IC far above the price ceiling with otherwise perfect metrics.
VRP_SHAPE = GateMetrics(ic=0.547, sr=2.631, dsr=1.0, fold_stab=1.0)
# A believable forward-price IC with the same otherwise-perfect metrics.
HONEST_SHAPE = GateMetrics(ic=0.05, sr=2.631, dsr=1.0, fold_stab=1.0)


class TestASuspectIcCannotGradeEdge:
    def test_the_measured_vrp_cell_no_longer_grades_edge(self) -> None:
        assert select_research_verdict(VRP_SHAPE, gate_lane=GATE_LANE_IC) != "edge"

    def test_it_caps_at_scout_rather_than_being_killed(self) -> None:
        """Not proven fake -- proven undeclared. Scout keeps it alive for the emitter to fix."""
        assert select_research_verdict(VRP_SHAPE, gate_lane=GATE_LANE_IC) == "scout"

    def test_every_measured_promoted_ic_is_now_capped(self) -> None:
        # The two signatures the 11 promoted books collapse into.
        for ic in (0.547, 0.500):
            metrics = GateMetrics(ic=ic, sr=2.631, dsr=1.0, fold_stab=1.0)

            assert select_research_verdict(metrics, gate_lane=GATE_LANE_IC) == "scout"

    def test_a_negative_suspect_ic_is_capped_too(self) -> None:
        """The gate scores abs(ic), so the ceiling must apply to abs(ic) as well."""
        metrics = GateMetrics(ic=-0.547, sr=2.631, dsr=1.0, fold_stab=1.0)

        assert select_research_verdict(metrics, gate_lane=GATE_LANE_IC) == "scout"

    def test_exactly_at_the_ceiling_is_still_allowed(self) -> None:
        """The flag fires ABOVE the ceiling, so the gate must use the same boundary."""
        metrics = GateMetrics(ic=PRICE_IC_CEILING, sr=2.631, dsr=1.0, fold_stab=1.0)

        assert select_research_verdict(metrics, gate_lane=GATE_LANE_IC) == "edge"


class TestTheEmitterCanStillDeclareItsLane:
    def test_declaring_the_book_lane_restores_the_grade(self) -> None:
        """The book lane ignores IC entirely, so a non-price target is graded on SR/DSR/folds."""
        assert select_research_verdict(VRP_SHAPE, gate_lane=GATE_LANE_BOOK) == "edge"

    def test_the_book_lane_is_not_a_free_pass(self) -> None:
        weak = GateMetrics(ic=0.547, sr=0.1, dsr=0.0, fold_stab=0.0)

        assert select_research_verdict(weak, gate_lane=GATE_LANE_BOOK) != "edge"


class TestAnHonestIcIsUntouched:
    def test_a_believable_price_ic_still_grades_edge(self) -> None:
        assert select_research_verdict(HONEST_SHAPE, gate_lane=GATE_LANE_IC) == "edge"

    def test_an_unknown_lane_still_fails_closed_to_the_ic_gate(self) -> None:
        assert select_research_verdict(VRP_SHAPE, gate_lane="something-else") == "scout"
