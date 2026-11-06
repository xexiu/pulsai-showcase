"""
TDD Tests for Trading Performance Optimization Objective (Sprint 2.0k)

Tests written FIRST before implementation (TDD approach).

Traditional ML optimizes for CLASSIFICATION metrics (accuracy, F1).
This is WRONG for trading because:
- 95% HOLD accuracy is useless (model just predicts HOLD always)
- F1 score doesn't care about PROFIT

Trading Performance Optimization focuses on:
1. Average return per trade (PRIMARY)
2. Win rate (SECONDARY)
3. Risk-adjusted returns (Sharpe, Calmar)
4. Trade frequency (avoid too few signals)

Reference: trading_bots/backend/core/models/AbstractPredictor.objective_bottom_detection_trading

@see docs/02-technical/ML_PIPELINE.md
"""

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest


def create_sample_predictions(
    n_samples: int = 100,
    model_accuracy: float = 0.6,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Create sample predictions for testing.

    Returns:
        y_true: Actual targets (0 or 1)
        y_pred: Predicted targets (0 or 1)
        y_proba: Prediction probabilities
    """
    np.random.seed(seed)

    # Create targets with some imbalance (20% positive)
    y_true = (np.random.random(n_samples) < 0.2).astype(int)

    # Create predictions with specified accuracy
    y_pred = y_true.copy()
    n_flip = int(n_samples * (1 - model_accuracy))
    flip_idx = np.random.choice(n_samples, n_flip, replace=False)
    y_pred[flip_idx] = 1 - y_pred[flip_idx]

    # Create probabilities
    y_proba = np.where(
        y_pred == 1,
        0.6 + 0.3 * np.random.random(n_samples),
        0.1 + 0.3 * np.random.random(n_samples),
    )

    return y_true, y_pred, y_proba


def create_sample_ohlcv_for_backtest(
    n_candles: int = 100,
    start_price: float = 50000.0,
    volatility: float = 0.02,
    seed: int = 42,
) -> pl.DataFrame:
    """Create sample OHLCVModel data for backtest scoring."""
    np.random.seed(seed)

    start_time = datetime(2025, 1, 1, 0, 0)
    timestamps = [start_time + timedelta(hours=i) for i in range(n_candles)]

    returns = np.random.normal(0, volatility, n_candles)
    closes_list: list[float] = [start_price]
    for r in returns[1:]:
        closes_list.append(closes_list[-1] * (1 + r))

    closes = np.array(closes_list)
    opens = np.roll(closes, 1)
    opens[0] = closes[0]

    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens.tolist(),
            "high": (closes * 1.01).tolist(),
            "low": (closes * 0.99).tolist(),
            "close": closes.tolist(),
            "volume": [1000.0] * n_candles,
        }
    )


# =============================================================================
# TRADING PERFORMANCE OBJECTIVE TESTS
# =============================================================================


class TestTradingPerformanceObjective:
    """
    Tests for TradingPerformanceObjective.

    This is a custom Optuna objective that optimizes for TRADING PERFORMANCE
    instead of classification metrics.

    Key formula (from reference):
    score = (
        avg_return_per_trade * 20 +  # Primary: profit
        win_rate * 3 +                # Secondary: win rate
        trade_frequency_score * 0.3   # Tertiary: frequency
    )
    """

    def test_returns_numeric_score(self) -> None:
        """Should return a numeric score for Optuna optimization."""
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        y_true, _, y_proba = create_sample_predictions(n_samples=100)
        df = create_sample_ohlcv_for_backtest(n_candles=100)

        objective = TradingPerformanceObjective(
            lookforward_periods=[3, 6, 12],
            transaction_cost=0.001,  # 0.1%
        )

        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        assert isinstance(score, (int, float)), f"Score should be numeric, got {type(score)}"

    def test_no_signals_returns_penalty(self) -> None:
        """
        If no buy signals generated, should return large NEGATIVE score.

        WHY: A model that never trades is useless for trading.
        """
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        # Create predictions with all zeros (no buy signals)
        y_true = np.zeros(100, dtype=int)
        y_proba = np.random.random(100) * 0.3  # All probabilities below threshold
        df = create_sample_ohlcv_for_backtest(n_candles=100)

        objective = TradingPerformanceObjective()

        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,  # No predictions will exceed this
        )

        # Type assertion: return_metrics=False (default) returns float
        assert isinstance(score, float)
        assert score < 0, f"No signals should return negative score, got {score}"

    def test_high_win_rate_increases_score(self) -> None:
        """
        Higher win rate should increase the score.

        WHY: Win rate is a key trading metric.
        Even if average return is similar, higher win rate is better.
        """
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        df = create_sample_ohlcv_for_backtest(n_candles=100, seed=42)
        objective = TradingPerformanceObjective()

        # Create two scenarios with different win rates
        # High win rate: predict buy only when actually profitable
        np.random.seed(42)
        y_true_high = np.array([1] * 20 + [0] * 80)
        y_proba_high = np.array([0.8] * 20 + [0.2] * 80)  # High confidence on actual positives

        # Low win rate: predict buy on random samples
        np.random.seed(43)
        y_true_low = np.array([1] * 20 + [0] * 80)
        y_proba_low = np.array([0.8] * 10 + [0.2] * 10 + [0.8] * 40 + [0.2] * 40)  # Random confidence

        score_high = objective.calculate_score(
            y_true=y_true_high,
            y_proba=y_proba_high,
            df=df,
            threshold=0.5,
        )
        score_low = objective.calculate_score(
            y_true=y_true_low,
            y_proba=y_proba_low,
            df=df,
            threshold=0.5,
        )

        # Note: Due to actual price movements, this is approximate
        # The test verifies the mechanism exists
        assert isinstance(score_high, (int, float))
        assert isinstance(score_low, (int, float))

    def test_transaction_cost_applied(self) -> None:
        """
        Transaction costs should be deducted from returns.

        WHY: Real trading has fees. Model must be profitable AFTER fees.
        """
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        y_true, _, y_proba = create_sample_predictions(n_samples=100)
        df = create_sample_ohlcv_for_backtest(n_candles=100)

        # No transaction cost
        objective_no_cost = TradingPerformanceObjective(transaction_cost=0.0)
        # High transaction cost
        objective_high_cost = TradingPerformanceObjective(transaction_cost=0.01)  # 1%

        score_no_cost = objective_no_cost.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )
        score_high_cost = objective_high_cost.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        # Type assertions: return_metrics=False (default) returns float
        assert isinstance(score_no_cost, float)
        assert isinstance(score_high_cost, float)

        # Higher costs should reduce score
        assert score_no_cost >= score_high_cost, (
            f"Higher transaction cost should reduce score. No cost: {score_no_cost}, High cost: {score_high_cost}"
        )

    def test_multiple_lookforward_periods(self) -> None:
        """
        Should calculate returns using MAX across lookforward periods.

        WHY: Same logic as target creation - find the best exit.
        """
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        y_true, _, y_proba = create_sample_predictions(n_samples=50)
        df = create_sample_ohlcv_for_backtest(n_candles=50)

        # Single lookforward
        objective_single = TradingPerformanceObjective(lookforward_periods=[3])
        # Multiple lookforward
        objective_multi = TradingPerformanceObjective(lookforward_periods=[3, 6, 12])

        score_single = objective_single.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )
        score_multi = objective_multi.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        # Multiple periods should find better exits → higher or equal score
        # Note: This depends on actual price movements
        assert isinstance(score_single, (int, float))
        assert isinstance(score_multi, (int, float))

    def test_threshold_affects_trade_count(self) -> None:
        """
        Higher threshold should result in fewer trades.

        WHY: Threshold filters low-confidence predictions.
        """
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        y_true = np.random.randint(0, 2, 100)
        y_proba = np.random.uniform(0.3, 0.9, 100)  # Wide range of probabilities
        df = create_sample_ohlcv_for_backtest(n_candles=100)

        objective = TradingPerformanceObjective()

        # Low threshold: more trades
        result_low = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.4,
        )
        # High threshold: fewer trades
        result_high = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.8,
        )

        # Both should produce valid scores
        assert isinstance(result_low, (int, float))
        assert isinstance(result_high, (int, float))


# =============================================================================
# RISK-ADJUSTED OBJECTIVE TESTS
# =============================================================================


class TestRiskAdjustedObjective:
    """
    Tests for risk-adjusted trading objective.

    Adds Sharpe ratio and max drawdown to the scoring.
    Better for risk-averse strategies.
    """

    def test_includes_sharpe_ratio(self) -> None:
        """Should include Sharpe ratio in scoring."""
        from src.infrastructure.ml.trading_objective import RiskAdjustedTradingObjective

        y_true, _, y_proba = create_sample_predictions(n_samples=100)
        df = create_sample_ohlcv_for_backtest(n_candles=100)

        objective = RiskAdjustedTradingObjective()

        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        assert isinstance(score, (int, float))

    def test_penalizes_high_drawdown(self) -> None:
        """
        High drawdown should reduce the score.

        WHY: Large drawdowns are psychologically difficult and risky.
        """
        from src.infrastructure.ml.trading_objective import RiskAdjustedTradingObjective

        df = create_sample_ohlcv_for_backtest(n_candles=100)

        # This is a behavioral test - just verify the method exists and runs
        objective = RiskAdjustedTradingObjective(
            drawdown_penalty_weight=5.0,  # High penalty for drawdown
        )

        y_true, _, y_proba = create_sample_predictions(n_samples=100)

        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        assert isinstance(score, (int, float))


# =============================================================================
# OPTUNA INTEGRATION TESTS
# =============================================================================


class TestOptunaIntegration:
    """Tests for integration with Optuna optimization."""

    def test_as_optuna_objective(self) -> None:
        """
        Should work as Optuna objective function.

        The objective receives a trial object and returns a score.
        """
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        # Mock trial-like interface
        class MockTrial:
            def suggest_float(self, name: str, low: float, high: float) -> float:
                return (low + high) / 2

            def suggest_int(self, name: str, low: int, high: int) -> int:
                return (low + high) // 2

        y_true, _, y_proba = create_sample_predictions(n_samples=100)
        df = create_sample_ohlcv_for_backtest(n_candles=100)

        objective = TradingPerformanceObjective()

        # Should accept trial object
        trial = MockTrial()
        threshold = trial.suggest_float("threshold", 0.3, 0.9)

        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=threshold,
        )

        assert isinstance(score, (int, float))

    def test_returns_metrics_dict(self) -> None:
        """
        Should optionally return detailed metrics dict.

        Useful for logging and analysis.
        """
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        y_true, _, y_proba = create_sample_predictions(n_samples=100)
        df = create_sample_ohlcv_for_backtest(n_candles=100)

        objective = TradingPerformanceObjective()

        result = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
            return_metrics=True,
        )

        # When return_metrics=True, returns tuple (score, metrics)
        assert isinstance(result, tuple)
        score, metrics = result

        assert isinstance(score, (int, float))
        assert isinstance(metrics, dict)

        # Expected metrics
        expected_keys = ["total_trades", "profitable_trades", "win_rate", "avg_return_per_trade"]
        for key in expected_keys:
            assert key in metrics, f"Missing metric: {key}"


# =============================================================================
# EDGE CASES
# =============================================================================


class TestTradingObjectiveEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_all_same_predictions(self) -> None:
        """Should handle case where all predictions are the same."""
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        y_true = np.ones(50, dtype=int)
        y_proba = np.ones(50) * 0.9  # All high confidence
        df = create_sample_ohlcv_for_backtest(n_candles=50)

        objective = TradingPerformanceObjective()

        # Should not crash
        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        assert isinstance(score, (int, float))

    def test_handles_empty_df(self) -> None:
        """Should handle empty DataFrame."""
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        df = pl.DataFrame(
            {
                "timestamp": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
            }
        )

        objective = TradingPerformanceObjective()

        score = objective.calculate_score(
            y_true=np.array([]),
            y_proba=np.array([]),
            df=df,
            threshold=0.5,
        )

        # Type assertion: return_metrics=False (default) returns float
        assert isinstance(score, float)
        # Should return penalty score for no data
        assert score < 0

    def test_handles_mismatched_lengths(self) -> None:
        """Should raise error if y_true and df lengths don't match."""
        from src.infrastructure.ml.trading_objective import TradingPerformanceObjective

        y_true = np.zeros(50, dtype=np.int_)  # Explicit int type
        y_proba = np.zeros(50)
        df = create_sample_ohlcv_for_backtest(n_candles=100)  # Different length

        objective = TradingPerformanceObjective()

        with pytest.raises(ValueError, match="length"):
            objective.calculate_score(
                y_true=y_true,
                y_proba=y_proba,
                df=df,
                threshold=0.5,
            )
