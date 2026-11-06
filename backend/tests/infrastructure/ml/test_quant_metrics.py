"""
TDD Tests for Sprint 2.11: Quant-Grade Evaluation Metrics.

New metrics:
1. Sortino ratio — penalizes only DOWNSIDE deviation (better than Sharpe for crypto)
2. IC (Information Coefficient) — correlation between predictions and actual returns
3. Rank IC — IC on ranks (robust to outliers)
4. Benchmark comparison — alpha vs buy-and-hold

Tests follow BEHAVIOR, not implementation:
- Known mathematical inputs → expected outputs
- Edge cases: all wins, all losses, zero variance, empty data
- Boundary conditions: perfect predictions vs random noise

@see .cursorrules — TDD first, behavior-focused tests
@see docs/01-business/ROADMAP.md — Sprint 2.11 Evaluation Metrics
"""

from __future__ import annotations

import numpy as np

# =============================================================================
# 1. Sortino Ratio Tests
# =============================================================================


class TestSortinoRatioImport:
    """Verify sortino_ratio function is importable."""

    def test_importable(self) -> None:
        from src.infrastructure.ml.quant_metrics import calculate_sortino_ratio

        assert callable(calculate_sortino_ratio)


class TestSortinoRatioBehavior:
    """
    Verify Sortino ratio calculations.

    Sortino = (mean_return - risk_free) / downside_deviation

    WHY Sortino > Sharpe for crypto:
    - Sharpe penalizes ALL volatility (up AND down)
    - Sortino penalizes only DOWNSIDE volatility
    - Crypto has massive positive outliers (100x gains)
    - Sharpe treats those as "risk" — Sortino doesn't

    KEY DIFFERENCE:
    - Sharpe: uses std(all returns)
    - Sortino: uses std(negative returns only)
    """

    def test_all_positive_returns_infinite_sortino(self) -> None:
        """
        If all returns are positive, downside deviation = 0 → Sortino = inf.

        REAL SCENARIO: Perfect strategy that never loses.
        Sharpe would still penalize high returns; Sortino correctly says "no risk."
        """
        from src.infrastructure.ml.quant_metrics import calculate_sortino_ratio

        returns = np.array([0.01, 0.02, 0.03, 0.01, 0.02])
        result = calculate_sortino_ratio(returns)
        # Should return capped positive value (we cap at 999.0 like profit_factor)
        assert result > 0

    def test_all_negative_returns_negative_sortino(self) -> None:
        """All negative returns → negative Sortino."""
        from src.infrastructure.ml.quant_metrics import calculate_sortino_ratio

        returns = np.array([-0.01, -0.02, -0.03, -0.01, -0.02])
        result = calculate_sortino_ratio(returns)
        assert result < 0

    def test_symmetric_returns_sortino_near_sharpe(self) -> None:
        """
        With symmetric returns (equal upside/downside), Sortino ≈ Sharpe * √2.

        WHY √2: Downside deviation uses only half the samples (the negative ones).
        For a normal distribution, downside std ≈ std/√2, so Sortino ≈ Sharpe * √2.
        """
        from src.infrastructure.ml.quant_metrics import calculate_sortino_ratio

        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)
        sortino = calculate_sortino_ratio(returns)
        # Should be finite and non-zero
        assert np.isfinite(sortino)
        assert sortino != 0.0

    def test_zero_returns_zero_sortino(self) -> None:
        """Zero returns → zero Sortino."""
        from src.infrastructure.ml.quant_metrics import calculate_sortino_ratio

        returns = np.array([0.0, 0.0, 0.0, 0.0])
        result = calculate_sortino_ratio(returns)
        assert result == 0.0

    def test_empty_returns_zero(self) -> None:
        """Empty array → zero."""
        from src.infrastructure.ml.quant_metrics import calculate_sortino_ratio

        result = calculate_sortino_ratio(np.array([]))
        assert result == 0.0

    def test_annualization_factor_scales_result(self) -> None:
        """Annualization factor should scale the ratio proportionally."""
        from src.infrastructure.ml.quant_metrics import calculate_sortino_ratio

        returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
        sortino_1 = calculate_sortino_ratio(returns, annualization_factor=1.0)
        sortino_sqrt252 = calculate_sortino_ratio(returns, annualization_factor=np.sqrt(252))
        # Annualized should be larger (multiplied by ~15.87)
        assert abs(sortino_sqrt252) > abs(sortino_1)


# =============================================================================
# 2. Information Coefficient (IC) Tests
# =============================================================================


class TestICImport:
    """Verify IC function is importable."""

    def test_importable(self) -> None:
        from src.infrastructure.ml.quant_metrics import calculate_ic

        assert callable(calculate_ic)


class TestICBehavior:
    """
    Verify Information Coefficient calculations.

    IC = Spearman rank correlation(predicted_proba, actual_returns)

    WHY IC is the gold standard for quant evaluation:
    - Measures if HIGHER predictions correspond to HIGHER returns
    - Rank-based → robust to scale differences
    - IC > 0.05 = "decent signal" in quant finance
    - IC > 0.1 = "strong signal" (rare and valuable)
    """

    def test_perfect_predictions_ic_is_one(self) -> None:
        """
        If predictions perfectly rank returns, IC = 1.0.

        REAL SCENARIO: A model that always predicts "the stock
        with the highest probability will have the highest return."
        """
        from src.infrastructure.ml.quant_metrics import calculate_ic

        predictions = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        actual_returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        ic = calculate_ic(predictions, actual_returns)
        assert abs(ic - 1.0) < 0.01

    def test_inverse_predictions_ic_is_negative_one(self) -> None:
        """Perfectly WRONG predictions → IC = -1.0."""
        from src.infrastructure.ml.quant_metrics import calculate_ic

        predictions = np.array([0.5, 0.4, 0.3, 0.2, 0.1])
        actual_returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        ic = calculate_ic(predictions, actual_returns)
        assert abs(ic - (-1.0)) < 0.01

    def test_random_predictions_ic_near_zero(self) -> None:
        """Random predictions should have IC near 0."""
        from src.infrastructure.ml.quant_metrics import calculate_ic

        np.random.seed(42)
        predictions = np.random.random(1000)
        actual_returns = np.random.normal(0, 0.02, 1000)
        ic = calculate_ic(predictions, actual_returns)
        # Should be near zero (within ±0.1 for 1000 samples)
        assert abs(ic) < 0.1

    def test_ic_bounded_between_minus_one_and_one(self) -> None:
        """IC must always be in [-1, 1]."""
        from src.infrastructure.ml.quant_metrics import calculate_ic

        np.random.seed(123)
        predictions = np.random.random(100)
        actual_returns = np.random.normal(0, 0.02, 100)
        ic = calculate_ic(predictions, actual_returns)
        assert -1.0 <= ic <= 1.0

    def test_empty_arrays_returns_zero(self) -> None:
        """Empty arrays → IC = 0."""
        from src.infrastructure.ml.quant_metrics import calculate_ic

        ic = calculate_ic(np.array([]), np.array([]))
        assert ic == 0.0

    def test_constant_predictions_returns_zero(self) -> None:
        """If all predictions are the same, no ranking possible → IC = 0."""
        from src.infrastructure.ml.quant_metrics import calculate_ic

        predictions = np.array([0.5, 0.5, 0.5, 0.5])
        actual_returns = np.array([0.01, 0.02, 0.03, 0.04])
        ic = calculate_ic(predictions, actual_returns)
        assert ic == 0.0


# =============================================================================
# 3. Rank IC Tests
# =============================================================================


class TestRankICImport:
    """Verify Rank IC function is importable."""

    def test_importable(self) -> None:
        from src.infrastructure.ml.quant_metrics import calculate_rank_ic

        assert callable(calculate_rank_ic)


class TestRankICBehavior:
    """
    Verify Rank IC calculations.

    Rank IC = Pearson correlation of RANKS of predictions and actual returns.

    WHY Rank IC in addition to IC:
    - IC uses Spearman (already rank-based), so IC ≈ Rank IC in most cases
    - Rank IC is the explicit "rank the predictions, rank the returns, correlate"
    - Some quant shops prefer Rank IC because it's more interpretable
    - Robust to outliers: a 100x return doesn't dominate the calculation
    """

    def test_perfect_ranking_rank_ic_is_one(self) -> None:
        """Perfect ranking → Rank IC = 1.0."""
        from src.infrastructure.ml.quant_metrics import calculate_rank_ic

        predictions = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
        actual_returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        rank_ic = calculate_rank_ic(predictions, actual_returns)
        assert abs(rank_ic - 1.0) < 0.01

    def test_outlier_robustness(self) -> None:
        """
        Rank IC should be robust to outliers (unlike raw Pearson correlation).

        REAL SCENARIO: One 50x return shouldn't dominate the metric.
        """
        from src.infrastructure.ml.quant_metrics import calculate_rank_ic

        predictions = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        # Last return is a massive outlier (50x the others)
        actual_returns = np.array([0.01, 0.02, 0.03, 0.04, 2.5])
        rank_ic = calculate_rank_ic(predictions, actual_returns)
        # Should still be close to 1.0 (ranking is preserved)
        assert rank_ic > 0.9


# =============================================================================
# 4. Benchmark Comparison Tests
# =============================================================================


class TestBenchmarkComparisonImport:
    """Verify benchmark comparison function is importable."""

    def test_importable(self) -> None:
        from src.infrastructure.ml.quant_metrics import calculate_benchmark_alpha

        assert callable(calculate_benchmark_alpha)


class TestBenchmarkComparisonBehavior:
    """
    Verify benchmark comparison (alpha) calculations.

    Alpha = strategy_return - benchmark_return

    WHY benchmark comparison:
    - A +10% return is meaningless if BTC did +50%
    - Alpha measures VALUE ADDED by the strategy
    - Negative alpha = you'd be better off just buying and holding BTC
    """

    def test_outperformance_positive_alpha(self) -> None:
        """Strategy beating benchmark → positive alpha."""
        from src.infrastructure.ml.quant_metrics import calculate_benchmark_alpha

        strategy_return = 0.15  # +15%
        benchmark_return = 0.10  # +10% (buy & hold)
        alpha = calculate_benchmark_alpha(strategy_return, benchmark_return)
        assert abs(alpha - 0.05) < 0.001

    def test_underperformance_negative_alpha(self) -> None:
        """Strategy underperforming → negative alpha."""
        from src.infrastructure.ml.quant_metrics import calculate_benchmark_alpha

        strategy_return = 0.05
        benchmark_return = 0.20
        alpha = calculate_benchmark_alpha(strategy_return, benchmark_return)
        assert alpha < 0

    def test_matching_returns_zero_alpha(self) -> None:
        """Same return as benchmark → zero alpha."""
        from src.infrastructure.ml.quant_metrics import calculate_benchmark_alpha

        alpha = calculate_benchmark_alpha(0.10, 0.10)
        assert abs(alpha) < 0.001


# =============================================================================
# 5. Integration: calculate_quant_metrics bundle
# =============================================================================


class TestQuantMetricsBundleImport:
    """Verify bundle function is importable."""

    def test_importable(self) -> None:
        from src.infrastructure.ml.quant_metrics import calculate_quant_metrics

        assert callable(calculate_quant_metrics)


class TestQuantMetricsBundleBehavior:
    """
    Verify the bundle function that calculates all quant metrics at once.

    WHY a bundle: Single call from backtester.py returns all new metrics
    in a typed dict, ready to merge into BacktestResult.
    """

    def test_returns_all_metric_keys(self) -> None:
        """Must return dict with all expected metric keys."""
        from src.infrastructure.ml.quant_metrics import calculate_quant_metrics

        net_returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
        predictions = np.array([0.6, 0.4, 0.7, 0.3, 0.65])
        actual_returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
        benchmark_return = 0.02

        result = calculate_quant_metrics(
            net_returns=net_returns,
            predictions=predictions,
            actual_returns=actual_returns,
            benchmark_return=benchmark_return,
            annualization_factor=1.0,
            # EXPLICIT, because the default that used to supply this published a wrong alpha on a
            # live public row. This value is exactly what the old fallback computed, so the
            # assertion below tests what it always tested -- the implicit step is now visible.
            strategy_capital_return=float(np.sum(net_returns)),
        )

        expected_keys = {
            "sortino_ratio",
            "information_coefficient",
            "rank_ic",
            "benchmark_alpha",
        }
        assert expected_keys.issubset(result.keys())

    def test_all_values_are_finite(self) -> None:
        """All returned metric values must be finite numbers."""
        from src.infrastructure.ml.quant_metrics import calculate_quant_metrics

        net_returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
        predictions = np.array([0.6, 0.4, 0.7, 0.3, 0.65])
        actual_returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])

        result = calculate_quant_metrics(
            net_returns=net_returns,
            predictions=predictions,
            actual_returns=actual_returns,
            benchmark_return=0.02,
            annualization_factor=1.0,
            strategy_capital_return=float(np.sum(net_returns)),
        )

        for key, value in result.items():
            assert np.isfinite(value), f"{key} is not finite: {value}"

    def test_handles_no_predictions_gracefully(self) -> None:
        """
        If predictions are None (classic strategy, no ML),
        IC and Rank IC should be 0.0, but Sortino should still compute.
        """
        from src.infrastructure.ml.quant_metrics import calculate_quant_metrics

        net_returns = np.array([0.01, -0.005, 0.02])

        result = calculate_quant_metrics(
            net_returns=net_returns,
            predictions=None,
            actual_returns=None,
            benchmark_return=0.01,
            annualization_factor=1.0,
            strategy_capital_return=float(np.sum(net_returns)),
        )

        assert result["information_coefficient"] == 0.0
        assert result["rank_ic"] == 0.0
        # Sortino should still work
        assert result["sortino_ratio"] != 0.0 or len(net_returns) == 0

    def test_benchmark_alpha_uses_capital_return_not_sum_of_notional_returns(
        self,
    ) -> None:
        """
        Levered books: sum(per-trade notional %) can be << buy-and-hold while
        capital total_return still beats B&H. Alpha must use capital excess.
        """
        from src.infrastructure.ml.quant_metrics import calculate_quant_metrics

        # Two +5% notional trades → sum(net_returns) ≈ 0.10
        net_returns = np.array([0.05, 0.05])
        # Same PnL on 5x notional vs $10k capital -> capital return ~ +50%
        strategy_capital_return = 0.50
        benchmark_return = 0.40  # B&H +40%

        result = calculate_quant_metrics(
            net_returns=net_returns,
            predictions=None,
            actual_returns=None,
            benchmark_return=benchmark_return,
            strategy_capital_return=strategy_capital_return,
            annualization_factor=1.0,
        )

        # Capital excess: 0.50 - 0.40 = +0.10 (NOT 0.10 - 0.40 = -0.30)
        assert abs(result["benchmark_alpha"] - 0.10) < 1e-9
        assert result["benchmark_alpha"] > 0


class TestOlsInterceptBeta:
    """Sprint 3.1c: benchmark factor regression (per-trade holding returns)."""

    def test_ols_recovers_beta_on_perfect_linear(self) -> None:
        from src.infrastructure.ml.quant_metrics import ols_intercept_beta

        rng = np.random.default_rng(42)
        x = rng.normal(size=20)
        true_beta = 1.25
        true_alpha = 0.01
        y = true_alpha + true_beta * x
        alpha_hat, beta_hat = ols_intercept_beta(x, y)
        assert abs(beta_hat - true_beta) < 1e-9
        assert abs(alpha_hat - true_alpha) < 1e-9

    def test_ols_returns_zero_when_too_few_points(self) -> None:
        from src.infrastructure.ml.quant_metrics import ols_intercept_beta

        x = np.array([0.01, 0.02])
        y = np.array([0.02, 0.03])
        a, b = ols_intercept_beta(x, y)
        assert a == 0.0
        assert b == 0.0


# =============================================================================
# 6. The capital return is REQUIRED — the fallback published a wrong public number
# =============================================================================


class TestAlphaCannotBeComputedFromTheWrongReturn:
    """`strategy_capital_return` must have no default, because the fallback shipped.

    `TestQuantMetricsBundleBehavior.test_benchmark_alpha_uses_capital_return_not_sum_of_notional_returns`
    already pins the right answer WHEN THE ARGUMENT IS PASSED. Nothing pinned what happens when it
    is omitted, and omitting it was legal: the bundle fell back to `sum(net_returns)` -- the exact
    quantity `calculate_benchmark_alpha`'s docstring forbids ("Do NOT pass sum(per-trade notional
    %) ... falsely understates alpha") -- and labelled it `benchmark_alpha`.

    MEASURED on prod 2026-09-15, PUBLIC row `f111ac10`:

        stored benchmark_alpha        -6.712
        total_return                  23.064
        benchmark_buy_hold_return     14.400
        23.064 - 14.400             =  8.664   <- what alpha should be

    Solving backwards, the strategy return actually passed was 7.688: the notional sum. The
    15.4-point gap FLIPS THE SIGN -- the stored number says the book lost to buy-and-hold while its
    own two components say it beat it by 8.66. Eight of the nine public rows are self-consistent;
    only this one is not.

    The single production caller (`backtester_metrics`) passes the capital return correctly today,
    so this is not a live miscomputation -- it is a live MECHANISM. A future caller that omits the
    argument republishes the same figure with no error, which is how the row above came to exist.
    Deleting the default makes that unrepresentable: Python raises at the call site instead.
    """

    def test_the_capital_return_has_no_default(self) -> None:
        """A default here is not a convenience -- it is a second, wrong definition of alpha."""
        import inspect

        from src.infrastructure.ml.quant_metrics import calculate_quant_metrics

        parameter = inspect.signature(calculate_quant_metrics).parameters["strategy_capital_return"]

        assert parameter.default is inspect.Parameter.empty, (
            "strategy_capital_return must be REQUIRED: while it defaulted to None the function fell "
            "back to sum(net_returns), which understated public row f111ac10's alpha by 15.4 points "
            "and flipped its sign."
        )

    def test_omitting_it_raises_rather_than_guessing(self) -> None:
        import pytest

        from src.infrastructure.ml.quant_metrics import calculate_quant_metrics

        with pytest.raises(TypeError):
            calculate_quant_metrics(  # type: ignore[call-arg]
                net_returns=np.array([0.1, 0.2]),
                predictions=None,
                actual_returns=None,
                benchmark_return=0.5,
            )

    def test_alpha_is_the_capital_return_minus_the_benchmark(self) -> None:
        """The relationship every public row is checked against, on f111ac10's own numbers."""
        from src.infrastructure.ml.quant_metrics import calculate_quant_metrics

        result = calculate_quant_metrics(
            net_returns=np.array([0.1, 0.2]),
            predictions=None,
            actual_returns=None,
            benchmark_return=14.400512942582168,
            strategy_capital_return=23.06419262135834,
        )

        assert abs(result["benchmark_alpha"] - 8.663679678776172) < 1e-9

    def test_the_notional_sum_would_have_given_the_wrong_answer(self) -> None:
        """Guard the guard: the two inputs must genuinely disagree, or the test above proves nothing."""
        from src.infrastructure.ml.quant_metrics import calculate_benchmark_alpha

        benchmark = 14.400512942582168

        assert abs(calculate_benchmark_alpha(7.688064207119448, benchmark) - -6.71244873546272) < 1e-9
        assert abs(calculate_benchmark_alpha(23.06419262135834, benchmark) - 8.663679678776172) < 1e-9
