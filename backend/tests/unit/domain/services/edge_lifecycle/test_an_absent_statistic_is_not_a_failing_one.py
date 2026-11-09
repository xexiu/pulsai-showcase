"""A statistic that was never measured must not read as a statistic that failed.

importers/callers : none - pytest collects this module
affected API      : none
data schemas      : none

MEASURED 2026-09-20 over 7,617 hunt cells in `src/research/edge_hunt/results`:

    gate_lane=ic AND ic is NaN/absent : 147
    ...of those, decision=kill        : 124
    ...account SURVIVED and grew      : 100
    ...AND beats_bh_both=True         :  21   <-- killed while beating buy-and-hold

Among the 21 are vt-17 cells finishing at $53.2M, $64.3M and $29.4M, and every
`ema200_bos_fvg` timeframe. `ema200_bos_fvg_sl2_tp4__btc_4h` runs 2021-01-01..2026-08-20
(12,342 bars, 5.6 years), spot $21,760 with ZERO liquidations, perp_3x $77,426,
`beats_bh_both: True` -- graded `null` -> `kill`.

WHY IT HAPPENS. `_verdict_ladder` compares `abs(ic) > THRESHOLD`. Every comparison against
NaN is False, so a cell with no IC fails EVERY rung and lands on "null". NaN does not fail
one threshold, it fails all of them silently.

The same function ALREADY decided the opposite for DSR, three lines away:

    dsr_ok_cand = m.dsr >= CANDIDATE_DSR_MIN or math.isnan(m.dsr)
    # "DSR NaN is 'unknown' and does not by itself block CANDIDATE."

So the repo's own rule is: an UNKNOWN statistic may not buy the top tier (EDGE
auto-promotes to production), but it must not BLOCK the middle one. IC and fold_stab were
left out of that rule. These tests put them in it.

A rule-based book (EMA200 + BOS/CHoCH + FVG) has no trained weights and produces no
meaningful directional rank-IC, and running zero walk-forward folds makes `fold_stab` the
undefined quantity 0/0 -- NaN, never 0.0. Reporting 0.0 asserts "no fold was positive",
which is a different and false claim.
"""

from __future__ import annotations

import math

import pytest

from src.domain.services.edge_lifecycle.gate import (
    CANDIDATE_DSR_MIN,
    CANDIDATE_FOLD_STAB_MIN,
    CANDIDATE_IC_MIN,
    GATE_LANE_IC,
    GateMetrics,
    select_research_verdict,
)

#: The measured `ema200_bos_fvg_sl2_tp4__btc_4h` cell: 5.6 years, spot $21,760, 0 liquidations,
#: perp_3x $77,426, beats_bh_both True. Its IC is NaN and it ran no folds.
EMA200_4H = GateMetrics(ic=math.nan, sr=1.100, dsr=0.993, fold_stab=math.nan)


class TestAnAbsentStatisticDoesNotKill:
    def test_a_money_making_book_with_no_ic_is_at_least_candidate(self) -> None:
        """The defect, in one line: this cell graded `null` and was archived."""
        verdict = select_research_verdict(EMA200_4H, gate_lane=GATE_LANE_IC)

        assert verdict == "candidate", (
            f"a book running 5.6 years, surviving every leverage lane with 0 liquidations and "
            f"beating buy-and-hold at 3x graded {verdict!r} because its rank-IC is NaN"
        )

    def test_an_absent_fold_stability_does_not_block_candidate(self) -> None:
        """Zero folds is 0/0 = undefined, not 'no fold was positive'."""
        no_folds = GateMetrics(ic=0.05, sr=1.0, dsr=0.99, fold_stab=math.nan)

        assert select_research_verdict(no_folds, gate_lane=GATE_LANE_IC) == "candidate"


class TestTheGateStillGrades:
    """Canaries. Without these the fix above is indistinguishable from deleting the gate."""

    def test_a_measured_bad_ic_is_still_rejected(self) -> None:
        """A real IC below the floor must still be judged -- NaN is unknown, 0.001 is bad."""
        measured_bad = GateMetrics(ic=0.001, sr=1.0, dsr=0.99, fold_stab=0.9)

        assert select_research_verdict(measured_bad, gate_lane=GATE_LANE_IC) != "candidate"

    def test_a_measured_zero_fold_stability_is_still_rejected(self) -> None:
        """Folds that RAN and were all negative is evidence, and must still block."""
        folds_all_negative = GateMetrics(ic=0.05, sr=1.0, dsr=0.99, fold_stab=0.0)

        assert select_research_verdict(folds_all_negative, gate_lane=GATE_LANE_IC) != "candidate"

    def test_an_unknown_ic_cannot_buy_edge(self) -> None:
        """EDGE auto-promotes to production. An unmeasured statistic must never earn it."""
        strong_but_no_ic = GateMetrics(ic=math.nan, sr=3.0, dsr=0.99, fold_stab=0.95)

        assert select_research_verdict(strong_but_no_ic, gate_lane=GATE_LANE_IC) != "edge"

    def test_an_unknown_fold_stability_cannot_buy_edge(self) -> None:
        strong_but_no_folds = GateMetrics(ic=0.05, sr=3.0, dsr=0.99, fold_stab=math.nan)

        assert select_research_verdict(strong_but_no_folds, gate_lane=GATE_LANE_IC) != "edge"

    def test_a_weak_sharpe_is_still_rejected_however_unknown_the_rest(self) -> None:
        """SR is measured here, so it keeps its full blocking power."""
        weak = GateMetrics(ic=math.nan, sr=0.1, dsr=math.nan, fold_stab=math.nan)

        assert select_research_verdict(weak, gate_lane=GATE_LANE_IC) != "candidate"

    @pytest.mark.parametrize(
        ("name", "threshold"),
        [
            ("CANDIDATE_IC_MIN", CANDIDATE_IC_MIN),
            ("CANDIDATE_DSR_MIN", CANDIDATE_DSR_MIN),
            ("CANDIDATE_FOLD_STAB_MIN", CANDIDATE_FOLD_STAB_MIN),
        ],
    )
    def test_the_thresholds_this_fix_relies_on_still_exist(self, name: str, threshold: float) -> None:
        """Fails loudly if a threshold is renamed away, rather than passing vacuously."""
        assert isinstance(threshold, float), name
