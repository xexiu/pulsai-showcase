"""Behaviour tests for the canonical edge-hunt gate (SoT verdict / promote / retention)."""

from __future__ import annotations

import inspect
import math

from src.domain.services.edge_lifecycle.gate import (
    GATE_LANE_BOOK,
    GATE_LANE_IC,
    GateMetrics,
    capital_backtest_passes,
    guarded_research_verdict,
    implausible_metrics,
    promote_decision,
    research_verdict,
    research_verdict_book,
    retention_decision,
    select_research_verdict,
)


class TestResearchVerdictBook:
    """Book lane: SR/DSR/fold_stab only — IC must not gate (execution books)."""

    def test_edge_without_ic_when_sr_dsr_fold_clear(self) -> None:
        # IC near zero / negative would kill IC-lane; book lane ignores IC.
        assert research_verdict_book(GateMetrics(ic=-0.04, sr=2.6, dsr=1.0, fold_stab=0.7)) == "edge"

    def test_edge_still_requires_sr_dsr_fold(self) -> None:
        assert research_verdict_book(GateMetrics(ic=0.0, sr=0.4, dsr=1.0, fold_stab=0.7)) != "edge"
        assert research_verdict_book(GateMetrics(ic=0.0, sr=0.8, dsr=0.80, fold_stab=0.7)) == "candidate"
        assert research_verdict_book(GateMetrics(ic=0.0, sr=0.8, dsr=0.95, fold_stab=0.4)) != "edge"

    def test_candidate_band_ignores_ic(self) -> None:
        assert research_verdict_book(GateMetrics(ic=0.0, sr=0.4, dsr=0.80, fold_stab=0.55)) == "candidate"

    def test_scout_when_sr_positive_but_below_candidate(self) -> None:
        assert research_verdict_book(GateMetrics(ic=0.0, sr=0.1, dsr=0.2, fold_stab=0.3)) == "scout"

    def test_null_when_sr_nonpositive(self) -> None:
        assert research_verdict_book(GateMetrics(ic=0.5, sr=-0.1, dsr=0.99, fold_stab=0.9)) == "null"

    def test_select_research_verdict_routes_by_lane(self) -> None:
        # Weak |IC| → IC-lane SCOUT; same SR/DSR/fold → book-lane EDGE.
        m = GateMetrics(ic=-0.005, sr=2.6, dsr=1.0, fold_stab=0.7)
        assert select_research_verdict(m, gate_lane=GATE_LANE_IC) == "scout"
        assert select_research_verdict(m, gate_lane=GATE_LANE_BOOK) == "edge"

    def test_edge_requires_all_four_thresholds(self) -> None:
        assert research_verdict(GateMetrics(ic=0.03, sr=0.8, dsr=0.95, fold_stab=0.7)) == "edge"

    def test_edge_downgrades_to_candidate_when_dsr_below_edge_bar(self) -> None:
        # strong IC/SR/fold but dsr 0.80 < 0.90 edge bar -> candidate, not edge
        assert research_verdict(GateMetrics(ic=0.03, sr=0.8, dsr=0.80, fold_stab=0.7)) == "candidate"

    def test_candidate_band(self) -> None:
        assert research_verdict(GateMetrics(ic=0.015, sr=0.4, dsr=0.80, fold_stab=0.55)) == "candidate"

    def test_a_low_dsr_does_not_block_candidate(self) -> None:
        """LENIENT-2 (owner 2026-10-04): DSR is a disclosure on the CANDIDATE rung, never a veto.
        Measured: 66 of 1,331 stored hunt cells moved scout -> candidate, 38 of them beating B&H."""
        assert research_verdict(GateMetrics(ic=0.015, sr=0.4, dsr=0.20, fold_stab=0.55)) == "candidate"

    def test_edge_still_requires_the_dsr_bar(self) -> None:
        """EDGE auto-promotes to production, so DSR keeps its full weight on that one rung."""
        assert research_verdict(GateMetrics(ic=0.03, sr=0.8, dsr=0.20, fold_stab=0.7)) == "candidate"

    def test_candidate_allowed_when_dsr_nan(self) -> None:
        assert research_verdict(GateMetrics(ic=0.015, sr=0.4, dsr=math.nan, fold_stab=0.55)) == "candidate"

    def test_scout_band(self) -> None:
        assert research_verdict(GateMetrics(ic=0.005, sr=0.1, dsr=0.2, fold_stab=0.3)) == "scout"

    def test_null_when_no_signal(self) -> None:
        assert research_verdict(GateMetrics(ic=-0.001, sr=-0.2, dsr=0.0, fold_stab=0.1)) == "null"

    def test_sign_flipped_ic_still_scores_via_abs(self) -> None:
        # negative IC of real magnitude + positive SR -> at least SCOUT (sign-corrected downstream)
        assert research_verdict(GateMetrics(ic=-0.03, sr=0.2, dsr=0.5, fold_stab=0.4)) == "scout"


class TestCapitalGate:
    def test_passes_when_final_exceeds_initial(self) -> None:
        assert capital_backtest_passes(10_000.0, 14_200.0) is True

    def test_fails_when_final_not_above_initial(self) -> None:
        assert capital_backtest_passes(10_000.0, 10_000.0) is False
        assert capital_backtest_passes(10_000.0, 8_500.0) is False

    def test_fails_on_bad_inputs(self) -> None:
        assert capital_backtest_passes(0.0, 5.0) is False
        assert capital_backtest_passes(math.nan, 5.0) is False
        assert capital_backtest_passes(10_000.0, math.inf) is False


class TestPromoteDecision:
    def test_edge_with_capital_pass_auto_promotes(self) -> None:
        assert promote_decision("edge", capital_pass=True) == "auto_promote_edge"

    def test_edge_without_capital_holds_as_candidate(self) -> None:
        assert promote_decision("edge", capital_pass=False) == "hold_candidate"

    def test_candidate_never_auto_promotes(self) -> None:
        assert promote_decision("candidate", capital_pass=True) == "no_promote"


class TestRetentionDecision:
    def test_edge_kept_and_r2_when_capital_passes(self) -> None:
        assert retention_decision("edge", capital_pass=True) == "keep_and_r2"

    def test_candidate_always_keep_and_r2_for_chart_display(self) -> None:
        # Display R2 ≠ prod promote; capital failure must not hide CANDIDATE from FULL chart.
        assert retention_decision("candidate", capital_pass=False) == "keep_and_r2"
        assert retention_decision("candidate", capital_pass=True) == "keep_and_r2"

    def test_scout_kept_local(self) -> None:
        assert retention_decision("scout", capital_pass=False) == "keep_local"

    def test_nice_to_have_survives_only_with_capital_pass(self) -> None:
        assert retention_decision("nice_to_have", capital_pass=True) == "keep_and_r2"
        assert retention_decision("nice_to_have", capital_pass=False) == "archive"

    def test_null_archived(self) -> None:
        assert retention_decision("null", capital_pass=True) == "archive"
        assert retention_decision("kill", capital_pass=False) == "archive"


class TestImplausibleMetricsGuard:
    """A verdict must never be issued on physically impossible numbers.

    Real corpus cells reached EDGE on metrics that cannot occur: `vrpband_l0__sa_4h` graded
    ic=1.0 / sr=62.7 / final_capital=$3.9e39 from $10k, because a VRP *level* series was passed
    where per-bar net RETURNS are expected and `fold_ics` was literally `sign(mean)` (so the IC
    term auto-passed at +/-1). The gate accepted all of it — it had no plausibility floor.
    Reference points: the corpus's best genuine books run ann-SR 1.3 (vt-17) to 2.9 (VRP), and
    published practice treats a backtest Sharpe above ~3 as a methodology-error signal.
    """

    def test_absurd_sharpe_is_null_not_edge(self) -> None:
        m = GateMetrics(ic=1.0, sr=62.695, dsr=1.0, fold_stab=1.0)
        assert research_verdict(m) == "edge", "precondition: the raw gate would grade this EDGE"
        assert implausible_metrics(m) != []
        assert guarded_research_verdict(m) == "null"

    def test_degenerate_unit_ic_is_flagged(self) -> None:
        m = GateMetrics(ic=1.0, sr=1.2, dsr=0.95, fold_stab=0.8)
        reasons = implausible_metrics(m)
        assert any("ic" in r for r in reasons)
        assert guarded_research_verdict(m) == "null"

    def test_impossible_wealth_multiple_is_flagged(self) -> None:
        m = GateMetrics(ic=0.05, sr=1.5, dsr=0.95, fold_stab=0.8)
        reasons = implausible_metrics(m, initial_capital=10_000.0, final_capital=3.9e39)
        assert any("wealth" in r for r in reasons)
        assert guarded_research_verdict(m, initial_capital=10_000.0, final_capital=3.9e39) == "null"

    def test_non_finite_wealth_is_flagged(self) -> None:
        m = GateMetrics(ic=0.05, sr=1.5, dsr=0.95, fold_stab=0.8)
        assert implausible_metrics(m, initial_capital=10_000.0, final_capital=math.inf) != []

    def test_a_genuinely_strong_book_still_passes(self) -> None:
        """VRP dvol_mom — the corpus's best real book — must NOT be caught by the guard."""
        m = GateMetrics(ic=0.05, sr=2.94, dsr=0.99, fold_stab=0.9)
        assert implausible_metrics(m, initial_capital=10_000.0, final_capital=42_000.0) == []
        assert guarded_research_verdict(m, initial_capital=10_000.0, final_capital=42_000.0) == "edge"

    def test_prod_1d_gb_modest_book_still_passes(self) -> None:
        m = GateMetrics(ic=0.03, sr=0.6, dsr=0.8, fold_stab=0.6)
        assert implausible_metrics(m) == []
        assert guarded_research_verdict(m) == "candidate"

    def test_guard_applies_to_the_book_lane_too(self) -> None:
        m = GateMetrics(ic=float("nan"), sr=62.7, dsr=1.0, fold_stab=1.0)
        assert research_verdict_book(m) == "edge", "precondition: raw book lane would grade EDGE"
        assert guarded_research_verdict(m, gate_lane=GATE_LANE_BOOK) == "null"

    def test_negative_absurd_sharpe_also_flagged(self) -> None:
        assert implausible_metrics(GateMetrics(ic=0.0, sr=-62.7, dsr=0.0, fold_stab=0.0)) != []

    def test_nan_metrics_do_not_crash_the_guard(self) -> None:
        nan = float("nan")
        assert implausible_metrics(GateMetrics(ic=nan, sr=nan, dsr=nan, fold_stab=nan)) == []


class TestThinSampleIsADisclosureNotAVeto:
    """A Sharpe from a handful of trades is a CAUTION, shown beside the result -- never a veto.

    History: 2026-08-03 the triage of 1,050 trained models ranked `8h/xgboost/v137` top on a recorded
    Sharpe of 4.48 from 30 trades, and a flat thin-sample rule was added HERE, inside the physical-
    possibility floor, where it nulled the verdict. Owner, 2026-10-04: everything in this repo is
    educational and research/money gates must not be strict -- a statistical caution is disclosed,
    not enforced. Thinness has ONE definition, ``cell_measurability.is_thin_sample`` (MinTRL with the
    flat floor as fallback), and the hunt cell carries it as ``capital_backtest.thin_sample``.
    """

    def test_high_sharpe_on_a_thin_sample_is_physically_possible(self) -> None:
        m = GateMetrics(ic=0.05, sr=4.48, dsr=0.9, fold_stab=0.8)
        assert implausible_metrics(m) == []

    def test_the_old_triage_leader_keeps_its_verdict(self) -> None:
        """8h/xgboost/v137: sr=4.48 on 30 trades. Thin, disclosed -- and graded on its numbers."""
        m = GateMetrics(ic=0.05, sr=4.48, dsr=1.0, fold_stab=1.0)
        assert guarded_research_verdict(m) != "null"

    def test_the_floor_takes_no_trade_count_at_all(self) -> None:
        """No second definition of thinness can creep back into the possibility floor."""
        assert "num_trades" not in inspect.signature(implausible_metrics).parameters
        assert "num_trades" not in inspect.signature(guarded_research_verdict).parameters
