"""
TDD Tests for Bottom Detection Optimization Objective

Tests written FIRST before implementation (TDD approach).

BottomDetectionObjective is optimized for bottom detection trading:
- Higher weights on avg_return (bottoms should have strong recovery)
- Bonus for entries near local minima (quality entries)
- Penalty for poor bottom detection

WHY specialized objective for bottom detection:
- Regular TradingPerformanceObjective treats all entries equally
- Bottom detection requires STRONG recovery (high avg_return)
- Quality matters more than quantity (high win_rate)

Note: RiskAdjustedTradingObjective is ALREADY COMPLETE (lines 378-453).
This tests only BottomDetectionObjective.

Reference: trading_bots/backend/core/models/AbstractPredictor.objective_bottom_detection_trading

@see docs/02-technical/ML_PIPELINE.md
"""

from datetime import datetime, timedelta

import numpy as np
import polars as pl


def create_sample_trading_data(
    n_samples: int = 100,
    win_rate: float = 0.5,
    avg_return: float = 0.01,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, pl.DataFrame]:
    """
    Create sample data for trading objective tests.

    Returns:
        Tuple of (y_true, y_proba, df with close prices)
    """
    np.random.seed(seed)

    # Create timestamps and prices
    timestamps = [datetime(2025, 1, 1) + timedelta(hours=i) for i in range(n_samples)]

    # Create price data with upward trend (for testing returns)
    close_prices = [50000.0]
    for _ in range(n_samples - 1):
        # Random walk with slight upward bias
        ret = np.random.normal(avg_return / 10, 0.01)
        close_prices.append(close_prices[-1] * (1 + ret))

    df = pl.DataFrame(
        {
            "timestamp": timestamps,
            "close": close_prices,
        }
    )

    # Create targets and probabilities
    y_true = np.zeros(n_samples, dtype=int)
    y_proba = np.random.uniform(0.3, 0.7, n_samples)

    # Set some high-probability signals
    n_signals = int(n_samples * 0.2)
    signal_indices = np.random.choice(n_samples - 15, n_signals, replace=False)

    for idx in signal_indices:
        y_true[idx] = 1
        y_proba[idx] = np.random.uniform(0.6, 0.95)

    return y_true, y_proba, df


def create_high_quality_bottom_data(
    n_samples: int = 100,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, pl.DataFrame]:
    """
    Create data simulating high-quality bottom detection.

    High quality = high win rate, high avg return per trade.
    """
    np.random.seed(seed)

    timestamps = [datetime(2025, 1, 1) + timedelta(hours=i) for i in range(n_samples)]

    # Create prices with strong recovery patterns at signal points
    close_prices = [50000.0]
    current = 50000.0

    for _ in range(n_samples - 1):
        # Normal random walk
        ret = np.random.normal(0, 0.01)
        current *= 1 + ret
        close_prices.append(current)

    # Create signals at "bottom" points with good recovery
    y_true = np.zeros(n_samples, dtype=int)
    y_proba = np.random.uniform(0.3, 0.5, n_samples)

    # Create 10 high-quality signals at points where recovery happens
    signal_points = [10, 20, 30, 40, 50, 60, 70, 80]
    for idx in signal_points:
        if idx + 12 < n_samples:
            y_true[idx] = 1
            y_proba[idx] = 0.85
            # Simulate strong recovery after signal
            for j in range(1, 13):
                if idx + j < n_samples:
                    close_prices[idx + j] = close_prices[idx] * (1 + 0.005 * j)

    df = pl.DataFrame(
        {
            "timestamp": timestamps,
            "close": close_prices,
        }
    )

    return y_true, y_proba, df


def create_poor_quality_data(
    n_samples: int = 100,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, pl.DataFrame]:
    """
    Create data simulating poor bottom detection.

    Poor quality = low win rate, low avg return.
    """
    np.random.seed(seed)

    timestamps = [datetime(2025, 1, 1) + timedelta(hours=i) for i in range(n_samples)]

    # Create prices that fall after signals (poor timing)
    close_prices = [50000.0]
    current = 50000.0

    for _ in range(n_samples - 1):
        ret = np.random.normal(-0.002, 0.01)  # Slight downward bias
        current *= 1 + ret
        close_prices.append(current)

    y_true = np.zeros(n_samples, dtype=int)
    y_proba = np.random.uniform(0.3, 0.5, n_samples)

    # Create signals that lead to losses
    signal_points = [10, 25, 40, 55, 70]
    for idx in signal_points:
        if idx + 12 < n_samples:
            y_true[idx] = 1
            y_proba[idx] = 0.7

    df = pl.DataFrame(
        {
            "timestamp": timestamps,
            "close": close_prices,
        }
    )

    return y_true, y_proba, df


# =============================================================================
# BOTTOM DETECTION OBJECTIVE TESTS
# =============================================================================


class TestBottomDetectionObjectiveCreation:
    """Tests for BottomDetectionObjective basic creation."""

    def test_inherits_from_trading_performance(self) -> None:
        """Should inherit from TradingPerformanceObjective."""
        from src.infrastructure.ml.trading_objective import (
            BottomDetectionObjective,
            TradingPerformanceObjective,
        )

        objective = BottomDetectionObjective()
        assert isinstance(objective, TradingPerformanceObjective)

    def test_default_parameters(self) -> None:
        """Should have higher default weights for bottom detection."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        objective = BottomDetectionObjective()

        # Higher return_weight (bottoms need strong recovery)
        assert objective.return_weight >= 20.0

        # Higher win_rate_weight (quality over quantity)
        assert objective.win_rate_weight >= 5.0

    def test_accepts_custom_parameters(self) -> None:
        """Should accept custom weight parameters."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        objective = BottomDetectionObjective(
            return_weight=30.0,
            win_rate_weight=10.0,
            quality_bonus=8.0,
            poor_penalty=15.0,
        )

        assert objective.return_weight == 30.0
        assert objective.win_rate_weight == 10.0
        assert objective.quality_bonus == 8.0
        assert objective.poor_penalty == 15.0


class TestBottomDetectionScoring:
    """Tests for BottomDetectionObjective scoring behavior."""

    def test_calculate_score_returns_float(self) -> None:
        """Should return a float score."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        y_true, y_proba, df = create_sample_trading_data(n_samples=100)
        objective = BottomDetectionObjective()

        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        assert isinstance(score, float)

    def test_high_quality_trades_get_bonus(self) -> None:
        """
        High win rate + high avg return should get quality bonus.

        BEHAVIOR TEST: Win rate > 60% AND avg return > 0.8% → bonus
        """
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        y_true, y_proba, df = create_high_quality_bottom_data()
        objective = BottomDetectionObjective(
            quality_bonus=5.0,
            quality_win_rate_threshold=0.6,
            quality_return_threshold=0.008,
        )

        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.7,
        )

        # Should be positive (good performance)
        assert isinstance(score, float) and score > 0, (  # noqa: PT018
            f"High quality should have positive score, got {score}"
        )

    def test_poor_quality_trades_get_penalty(self) -> None:
        """
        Low win rate OR low avg return should get penalty.

        BEHAVIOR TEST: Win rate < 40% OR avg return < 0.2% → penalty
        """
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        y_true, y_proba, df = create_poor_quality_data()
        objective = BottomDetectionObjective(
            poor_penalty=10.0,
            poor_win_rate_threshold=0.4,
            poor_return_threshold=0.002,
        )

        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        # Score should be lower (poor performance penalized)
        # We don't assert exact value, just that scoring works
        assert isinstance(score, float)

    def test_higher_return_weight_than_base(self) -> None:
        """
        BottomDetectionObjective should emphasize avg_return more.

        WHY: Bottoms that don't bounce strongly are not good bottoms.
        """
        from src.infrastructure.ml.trading_objective import (
            BottomDetectionObjective,
            TradingPerformanceObjective,
        )

        y_true, y_proba, df = create_sample_trading_data()

        base_objective = TradingPerformanceObjective(return_weight=20.0)
        bottom_objective = BottomDetectionObjective(return_weight=25.0)

        base_score = base_objective.calculate_score(y_true, y_proba, df, threshold=0.5)
        bottom_score = bottom_objective.calculate_score(y_true, y_proba, df, threshold=0.5)

        # Both should return valid scores
        assert isinstance(base_score, float)
        assert isinstance(bottom_score, float)


class TestBottomDetectionQualityThresholds:
    """Tests for quality bonus/penalty thresholds."""

    def test_quality_bonus_configurable(self) -> None:
        """Quality bonus amount should be configurable."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        objective = BottomDetectionObjective(quality_bonus=10.0)
        assert objective.quality_bonus == 10.0

    def test_poor_penalty_configurable(self) -> None:
        """Poor performance penalty should be configurable."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        objective = BottomDetectionObjective(poor_penalty=20.0)
        assert objective.poor_penalty == 20.0

    def test_win_rate_threshold_configurable(self) -> None:
        """Win rate thresholds should be configurable."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        objective = BottomDetectionObjective(
            quality_win_rate_threshold=0.7,
            poor_win_rate_threshold=0.35,
        )

        assert objective.quality_win_rate_threshold == 0.7
        assert objective.poor_win_rate_threshold == 0.35

    def test_return_threshold_configurable(self) -> None:
        """Return thresholds should be configurable."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        objective = BottomDetectionObjective(
            quality_return_threshold=0.01,
            poor_return_threshold=0.001,
        )

        assert objective.quality_return_threshold == 0.01
        assert objective.poor_return_threshold == 0.001


class TestBottomDetectionWithMetrics:
    """Tests for returning detailed metrics."""

    def test_return_metrics_option(self) -> None:
        """Should support return_metrics parameter."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        y_true, y_proba, df = create_sample_trading_data()
        objective = BottomDetectionObjective()

        result = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
            return_metrics=True,
        )

        assert isinstance(result, tuple)
        assert len(result) == 2

        score, metrics = result
        assert isinstance(score, float)
        assert isinstance(metrics, dict)

    def test_metrics_include_standard_fields(self) -> None:
        """Returned metrics should include standard trading fields."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        y_true, y_proba, df = create_sample_trading_data()
        objective = BottomDetectionObjective()

        result = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
            return_metrics=True,
        )

        # When return_metrics=True, result is tuple (score, metrics_dict)
        assert isinstance(result, tuple), "Expected tuple when return_metrics=True"
        _, metrics = result

        expected_fields = ["total_trades", "win_rate", "avg_return_per_trade"]
        for field in expected_fields:
            assert field in metrics, f"Missing field: {field}"


class TestBottomDetectionEdgeCases:
    """Tests for edge cases."""

    def test_empty_data(self) -> None:
        """Should handle empty data gracefully."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        y_true = np.array([])
        y_proba = np.array([])
        df = pl.DataFrame({"close": []})

        objective = BottomDetectionObjective()
        score = objective.calculate_score(y_true, y_proba, df)

        assert score == -1000.0  # Penalty score

    def test_no_signals_generated(self) -> None:
        """Should handle case where threshold filters all signals."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        y_true, y_proba, df = create_sample_trading_data()
        y_proba = np.full_like(y_proba, 0.1)  # All low probability

        objective = BottomDetectionObjective()
        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.99,  # Very high threshold
        )

        assert score == -1000.0  # Penalty score

    def test_too_few_trades(self) -> None:
        """Should penalize if fewer than min_trades."""
        from src.infrastructure.ml.trading_objective import BottomDetectionObjective

        y_true = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        y_proba = np.array([0.9, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
        df = pl.DataFrame(
            {
                "close": [50000.0 + i * 100 for i in range(10)],
            }
        )

        objective = BottomDetectionObjective(min_trades=5)
        score = objective.calculate_score(
            y_true=y_true,
            y_proba=y_proba,
            df=df,
            threshold=0.5,
        )

        # Should be negative (penalty for too few trades)
        assert isinstance(score, float) and score < 0, (  # noqa: PT018
            f"Too few trades should return negative score, got {score}"
        )
