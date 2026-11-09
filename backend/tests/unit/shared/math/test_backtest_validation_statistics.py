"""Behavior tests for the backtest validation-statistics SoT.

These guard the de Prado / Bailey validation primitives that reject
selection-biased, single-window, low-N "winners":

- Probabilistic & Deflated Sharpe Ratio (PSR/DSR) — Bailey & López de Prado.
- Expected maximum Sharpe under N trials — the False Strategy Theorem.
- Probability of Backtest Overfitting (PBO) via CSCV.
- A composite gate (≥ min-trades AND DSR ≥ confidence).

Ground truth for the normal CDF/inverse-CDF is taken from scipy in the tests
only; the production module is intentionally stdlib-only (import-cost-lean leaf).
"""

from __future__ import annotations

import math

import pytest
from scipy.stats import norm  # test-only ground truth

from src.shared.constants.backtest import BACKTEST_VALIDATION_MIN_TRADES
from src.shared.math.backtest_validation_statistics import (
    BacktestValidationVerdict,
    deflated_sharpe_ratio,
    estimate_oos_bars,
    evaluate_backtest_validation,
    expected_maximum_sharpe,
    format_oos_gate_tier,
    probabilistic_sharpe_ratio,
    probability_of_backtest_overfitting,
    resolve_research_min_trades,
)
from src.shared.math.oos_window import OosWindow, evaluate_oos_window_gate

# --------------------------------------------------------------------------- #
# Probabilistic Sharpe Ratio
# --------------------------------------------------------------------------- #


def test_psr_is_half_when_observed_equals_benchmark() -> None:
    """SR == SR* with normal returns → coin-flip confidence (0.5)."""
    psr = probabilistic_sharpe_ratio(0.8, 0.8, n_observations=500)
    assert psr == pytest.approx(0.5, abs=1e-9)


def test_psr_above_half_when_observed_beats_benchmark() -> None:
    assert probabilistic_sharpe_ratio(1.2, 0.5, n_observations=500) > 0.5


def test_psr_below_half_when_observed_under_benchmark() -> None:
    assert probabilistic_sharpe_ratio(0.2, 0.9, n_observations=500) < 0.5


def test_psr_more_observations_increases_confidence() -> None:
    """Same positive edge, more samples → more confident it is real."""
    few = probabilistic_sharpe_ratio(1.0, 0.5, n_observations=30)
    many = probabilistic_sharpe_ratio(1.0, 0.5, n_observations=5000)
    assert many > few


def test_psr_negative_skew_and_fat_tails_reduce_confidence() -> None:
    """Left-skewed, fat-tailed returns are penalized (lower PSR)."""
    gaussian = probabilistic_sharpe_ratio(1.0, 0.5, n_observations=500, skew=0.0, kurtosis=3.0)
    ugly = probabilistic_sharpe_ratio(1.0, 0.5, n_observations=500, skew=-1.5, kurtosis=9.0)
    assert ugly < gaussian


def test_psr_matches_closed_form_against_scipy() -> None:
    sr, sr_star, n = 1.1, 0.4, 250
    # Gaussian Sharpe-estimator variance (Lo/Mertens): 1 - skew*SR + (kurt-1)/4*SR^2
    # → 1 + 0.5*SR^2 when skew=0, kurt=3.
    denom = math.sqrt(1.0 + 0.5 * sr * sr)
    expected_z = (sr - sr_star) * math.sqrt(n - 1) / denom
    assert probabilistic_sharpe_ratio(sr, sr_star, n_observations=n) == pytest.approx(float(norm.cdf(expected_z)), abs=1e-6)


def test_psr_too_few_observations_returns_zero() -> None:
    assert probabilistic_sharpe_ratio(2.0, 0.0, n_observations=1) == 0.0


def test_psr_within_unit_interval() -> None:
    for sr in (-3.0, 0.0, 0.5, 4.0):
        p = probabilistic_sharpe_ratio(sr, 0.5, n_observations=300)
        assert 0.0 <= p <= 1.0


# --------------------------------------------------------------------------- #
# Expected maximum Sharpe (False Strategy Theorem)
# --------------------------------------------------------------------------- #


def test_expected_max_sharpe_increases_with_trials() -> None:
    assert expected_maximum_sharpe(100, 1.0) > expected_maximum_sharpe(5, 1.0)


def test_expected_max_sharpe_scales_linearly_with_std() -> None:
    base = expected_maximum_sharpe(50, 1.0)
    assert expected_maximum_sharpe(50, 2.0) == pytest.approx(2.0 * base, rel=1e-9)


def test_expected_max_sharpe_no_inflation_for_single_trial() -> None:
    assert expected_maximum_sharpe(1, 1.0) == 0.0
    assert expected_maximum_sharpe(0, 1.0) == 0.0


def test_expected_max_sharpe_zero_dispersion_is_zero() -> None:
    assert expected_maximum_sharpe(100, 0.0) == 0.0


def test_expected_max_sharpe_reference_value_n2() -> None:
    """Hand-derived: N=2,std=1 -> (1-g)*PhiInv(0.5) + g*PhiInv(1-1/(2e)) ~= 0.5772*0.900."""
    gamma = 0.5772156649015329
    hand = (1.0 - gamma) * float(norm.ppf(0.5)) + gamma * float(norm.ppf(1.0 - 1.0 / (2.0 * math.e)))
    assert expected_maximum_sharpe(2, 1.0) == pytest.approx(hand, abs=1e-4)


# --------------------------------------------------------------------------- #
# Deflated Sharpe Ratio
# --------------------------------------------------------------------------- #


def test_dsr_below_psr_when_many_trials() -> None:
    """Deflation for selection bias lowers confidence vs naive PSR-against-zero."""
    naive = probabilistic_sharpe_ratio(1.0, 0.0, n_observations=250)
    deflated = deflated_sharpe_ratio(1.0, n_trials=600, n_observations=250, trial_sharpe_std=0.5)
    assert deflated < naive


def test_dsr_rejects_low_n_single_window_winner() -> None:
    """The 27-trade, best-of-~600-trials case → DSR well below 0.95 (REJECT)."""
    dsr = deflated_sharpe_ratio(0.9, n_trials=600, n_observations=27, trial_sharpe_std=0.6)
    assert dsr < 0.95


def test_dsr_accepts_strong_low_trial_strategy() -> None:
    """High Sharpe, many observations, few trials → DSR clears 0.95."""
    dsr = deflated_sharpe_ratio(2.2, n_trials=3, n_observations=1000, trial_sharpe_std=0.2)
    assert dsr > 0.95


def test_dsr_within_unit_interval() -> None:
    dsr = deflated_sharpe_ratio(1.0, n_trials=50, n_observations=200, trial_sharpe_std=0.4)
    assert 0.0 <= dsr <= 1.0


# --------------------------------------------------------------------------- #
# Probability of Backtest Overfitting (CSCV)
# --------------------------------------------------------------------------- #


def test_pbo_zero_when_one_config_dominates_everywhere() -> None:
    """A config that wins in-sample and out-of-sample → no overfitting."""
    # rows = observations, cols = configs. col0 dominates in both slices.
    matrix = [
        [0.09, -0.11],
        [0.11, -0.09],
        [0.09, -0.11],
        [0.11, -0.09],
    ]
    assert probability_of_backtest_overfitting(matrix, n_slices=2) == pytest.approx(0.0, abs=1e-9)


def test_pbo_one_when_is_best_is_oos_worst() -> None:
    """Perfectly anti-persistent performance → certain overfit (PBO == 1)."""
    matrix = [
        [0.09, -0.11],  # slice 0: config0 wins
        [0.11, -0.09],
        [-0.11, 0.09],  # slice 1: config1 wins
        [-0.09, 0.11],
    ]
    assert probability_of_backtest_overfitting(matrix, n_slices=2) == pytest.approx(1.0, abs=1e-9)


def test_pbo_within_unit_interval() -> None:
    matrix = [[0.01 * ((r * 7 + c * 3) % 5 - 2) for c in range(4)] for r in range(12)]
    pbo = probability_of_backtest_overfitting(matrix, n_slices=4)
    assert 0.0 <= pbo <= 1.0


def test_pbo_rejects_odd_or_tiny_slice_count() -> None:
    matrix = [[0.1, 0.2], [0.1, 0.2], [0.1, 0.2], [0.1, 0.2]]
    with pytest.raises(ValueError, match="n_slices"):
        probability_of_backtest_overfitting(matrix, n_slices=3)
    with pytest.raises(ValueError, match="n_slices"):
        probability_of_backtest_overfitting(matrix, n_slices=1)


def test_pbo_rejects_single_config() -> None:
    matrix = [[0.1], [0.2], [0.1], [0.2]]
    with pytest.raises(ValueError, match="competing configs"):
        probability_of_backtest_overfitting(matrix, n_slices=2)


def test_pbo_rejects_excessive_slice_count() -> None:
    """Guard the combinatorial blow-up: C(n_slices, n_slices/2) must stay bounded."""
    matrix = [[0.01 * r, 0.02 * r] for r in range(40)]
    with pytest.raises(ValueError, match="<="):
        probability_of_backtest_overfitting(matrix, n_slices=22)


# --------------------------------------------------------------------------- #
# Composite validation gate
# --------------------------------------------------------------------------- #


def test_gate_fails_on_insufficient_trades() -> None:
    verdict = evaluate_backtest_validation(
        num_trades=27,
        observed_sharpe=0.9,
        n_trials=600,
        trial_sharpe_std=0.6,
    )
    assert isinstance(verdict, BacktestValidationVerdict)
    assert verdict.passed is False
    assert verdict.meets_min_trades is False
    assert any("trade" in r.lower() for r in verdict.reasons)


def test_gate_fails_on_weak_deflated_sharpe() -> None:
    verdict = evaluate_backtest_validation(
        num_trades=400,
        observed_sharpe=0.3,
        n_trials=600,
        trial_sharpe_std=0.6,
    )
    assert verdict.passed is False
    assert verdict.meets_min_trades is True
    assert verdict.meets_min_dsr is False


def test_gate_passes_strong_strategy() -> None:
    verdict = evaluate_backtest_validation(
        num_trades=1000,
        observed_sharpe=2.2,
        n_trials=3,
        trial_sharpe_std=0.2,
    )
    assert verdict.passed is True
    assert verdict.meets_min_trades is True
    assert verdict.meets_min_dsr is True
    assert verdict.reasons == ()


def test_gate_respects_custom_thresholds() -> None:
    verdict = evaluate_backtest_validation(
        num_trades=50,
        observed_sharpe=1.5,
        n_trials=10,
        trial_sharpe_std=0.3,
        min_trades=30,
        min_deflated_sharpe=0.5,
    )
    assert verdict.meets_min_trades is True


# --------------------------------------------------------------------------- #
# TF-scaled research min-trades + tiered OOS gates
# --------------------------------------------------------------------------- #


def test_estimate_oos_bars_4h_window() -> None:
    # 2026-03-02 .. 2026-06-08 = 98 calendar days -> 98 * 6 = 588 bars at 4h
    bars = estimate_oos_bars(timeframe="4h", start_date="2026-03-02", end_date="2026-06-08")
    assert bars == 588


def test_resolve_research_min_trades_slow_tf_floor() -> None:
    assert resolve_research_min_trades(98) == 30  # 1d-ish bar count
    assert resolve_research_min_trades(588) == 30  # 4h window: 588//20=29 -> floor 30


def test_resolve_research_min_trades_1h_scales_up() -> None:
    # ~2352 bars for same window at 1h -> 117, below cert cap
    assert resolve_research_min_trades(2352) == 117


def test_resolve_research_min_trades_caps_at_certification() -> None:
    assert resolve_research_min_trades(10_000) == BACKTEST_VALIDATION_MIN_TRADES


def test_scout_gate_passes_without_trade_floor() -> None:
    verdict = evaluate_oos_window_gate(
        net=1.5,
        profit_factor=1.2,
        num_trades=3,
        observed_sharpe=0.5,
        n_trials=40,
        trial_sharpe_std=0.0,
        window=OosWindow(timeframe="4h", start="2026-03-02", end="2026-06-08"),
    )
    assert verdict.scout_pass is True
    assert verdict.research_pass is False
    assert verdict.certification_pass is False


def test_research_gate_uses_tf_scaled_floor() -> None:
    """39 trades on 1d OOS clears research (floor 30) but not certification (200)."""
    verdict = evaluate_oos_window_gate(
        net=2.0,
        profit_factor=1.5,
        num_trades=39,
        observed_sharpe=2.2,
        n_trials=3,
        trial_sharpe_std=0.2,
        window=OosWindow(timeframe="1d", start="2026-03-02", end="2026-06-08"),
    )
    assert verdict.min_trades_research == 30
    assert verdict.scout_pass is True
    assert verdict.research_pass is True
    assert verdict.certification_pass is False


def test_research_min_trades_override_bypasses_tf_scale() -> None:
    verdict = evaluate_oos_window_gate(
        net=2.0,
        profit_factor=1.5,
        num_trades=15,
        observed_sharpe=2.2,
        n_trials=3,
        trial_sharpe_std=0.2,
        window=OosWindow(timeframe="1d", start="2026-03-02", end="2026-06-08"),
        research_min_trades_override=10,
    )
    assert verdict.min_trades_research == 10
    assert verdict.research_pass is True
    assert verdict.certification_pass is False


def test_tiered_gate_fails_scout_on_negative_net() -> None:
    verdict = evaluate_oos_window_gate(
        net=-1.0,
        profit_factor=1.5,
        num_trades=500,
        observed_sharpe=2.0,
        n_trials=3,
        trial_sharpe_std=0.2,
        window=OosWindow(timeframe="1h", start="2026-03-02", end="2026-06-08"),
    )
    assert verdict.scout_pass is False
    assert verdict.research_pass is False
    assert verdict.certification_pass is False


def test_format_oos_gate_tier_highest_wins() -> None:
    research = evaluate_oos_window_gate(
        net=2.0,
        profit_factor=1.5,
        num_trades=39,
        observed_sharpe=2.2,
        n_trials=3,
        trial_sharpe_std=0.2,
        window=OosWindow(timeframe="1d", start="2026-03-02", end="2026-06-08"),
    )
    assert format_oos_gate_tier(research, exploratory_pass=True) == "research"

    scout_only = evaluate_oos_window_gate(
        net=1.0,
        profit_factor=1.2,
        num_trades=3,
        observed_sharpe=0.5,
        n_trials=3,
        trial_sharpe_std=0.2,
        window=OosWindow(timeframe="1d", start="2026-03-02", end="2026-06-08"),
    )
    assert format_oos_gate_tier(scout_only, exploratory_pass=False) == "scout"
    assert format_oos_gate_tier(scout_only, exploratory_pass=True) == "exploratory"

    kill = evaluate_oos_window_gate(
        net=-1.0,
        profit_factor=0.8,
        num_trades=3,
        observed_sharpe=0.5,
        n_trials=3,
        trial_sharpe_std=0.2,
        window=OosWindow(timeframe="1d", start="2026-03-02", end="2026-06-08"),
    )
    assert format_oos_gate_tier(kill, exploratory_pass=False) == "kill"
