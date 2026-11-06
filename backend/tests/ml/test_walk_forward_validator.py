"""
TDD Tests for WalkForwardValidator

Tests written FIRST before implementation (TDD approach).
CRITICAL: Verifies no future data leakage in time-series validation.

@see docs/02-technical/ML_PIPELINE.md - Walk-Forward Validation
"""

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest


def create_time_series_data(
    n_samples: int = 1000,
    n_features: int = 14,
    start_date: datetime | None = None,
    seed: int = 42,
) -> pl.DataFrame:
    """
    Create time-series data for validation testing.

    Args:
        n_samples: Number of samples
        n_features: Number of features
        start_date: Start datetime (default: 2024-01-01)
        seed: Random seed

    Returns:
        Polars DataFrame with timestamp, features, and target
    """
    np.random.seed(seed)

    if start_date is None:
        start_date = datetime(2024, 1, 1)

    # Create timestamps (1h intervals)
    timestamps = [start_date + timedelta(hours=i) for i in range(n_samples)]

    # Create features
    feature_data = {f"feature_{i}": np.random.randn(n_samples).tolist() for i in range(n_features)}

    # Create target
    target = np.random.choice([-1, 0, 1], size=n_samples).tolist()

    return pl.DataFrame(
        {
            "timestamp": timestamps,
            **feature_data,
            "target": target,
        }
    )


class TestWalkForwardValidatorBasic:
    """Basic validator functionality tests."""

    def test_validator_initialization(self) -> None:
        """Validator should initialize with correct parameters."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=60,
            test_window_days=14,
            step_days=7,
        )

        assert validator.train_window_days == 60
        assert validator.test_window_days == 14
        assert validator.step_days == 7

    def test_creates_validation_folds(self) -> None:
        """Validator should create multiple validation folds."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=60,
            test_window_days=14,
            step_days=7,
        )

        df = create_time_series_data(n_samples=2400)  # 100 days of hourly data
        folds = validator.create_folds(df)

        assert len(folds) > 0, "Should create at least one fold"


class TestWalkForwardValidatorNoFutureLeak:
    """CRITICAL: Tests to ensure no future data leakage."""

    def test_train_end_before_test_start(self) -> None:
        """
        Train period must end before test period starts.

        train_end <= test_start is REQUIRED to prevent future leak.
        """
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = create_time_series_data(n_samples=2000)
        folds = validator.create_folds(df)

        for fold_idx, fold in enumerate(folds):
            train_end = fold["train_end"]
            test_start = fold["test_start"]

            assert train_end <= test_start, f"Fold {fold_idx}: train_end ({train_end}) must be <= test_start ({test_start})"

    def test_no_overlap_between_train_and_test(self) -> None:
        """Training and test sets must not overlap."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = create_time_series_data(n_samples=2000)
        folds = validator.create_folds(df)

        for fold_idx, fold in enumerate(folds):
            train_indices = set(range(fold["train_start_idx"], fold["train_end_idx"]))
            test_indices = set(range(fold["test_start_idx"], fold["test_end_idx"]))

            overlap = train_indices & test_indices
            assert len(overlap) == 0, f"Fold {fold_idx}: train and test overlap at {overlap}"

    def test_fold_dates_are_logged(self) -> None:
        """Each fold should have explicit date logging for verification."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = create_time_series_data(n_samples=2000)
        folds = validator.create_folds(df)

        for fold in folds:
            # Each fold should have date boundaries
            assert "train_start" in fold
            assert "train_end" in fold
            assert "test_start" in fold
            assert "test_end" in fold

            # Dates should be actual datetime objects
            assert isinstance(fold["train_start"], datetime)
            assert isinstance(fold["train_end"], datetime)


class TestWalkForwardValidatorRollingMode:
    """
    Rolling train window (backtest-hub style): fixed-length train that slides.

    Complements anchored mode (expanding train from series start).
    """

    def test_rolling_train_span_is_fixed_not_expanding(self) -> None:
        """Each fold's train calendar span equals train_window_days (rolling), not growing."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
            window_mode="rolling",
        )
        df = create_time_series_data(n_samples=4000)
        folds = validator.create_folds(df)
        assert len(folds) >= 2
        for fold in folds:
            span_days = (fold["train_end"] - fold["train_start"]).days
            assert span_days == 30, "rolling mode must keep fixed train length"

    def test_rolling_second_fold_train_starts_at_step_offset(self) -> None:
        """Second fold train_start advances by step_days (rolling geometry)."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
            window_mode="rolling",
        )
        df = create_time_series_data(n_samples=4000)
        folds = validator.create_folds(df)
        assert len(folds) >= 2
        delta = folds[1]["train_start"] - folds[0]["train_start"]
        assert delta == timedelta(days=7)

    def test_rolling_no_future_leak(self) -> None:
        """train_end + embargo <= test_start; indices do not overlap."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
            window_mode="rolling",
            embargo_days=3,
        )
        df = create_time_series_data(n_samples=4000)
        folds = validator.create_folds(df)
        assert len(folds) >= 1
        for fold in folds:
            assert fold["train_end"] <= fold["test_start"]
            assert (fold["test_start"] - fold["train_end"]).days == 3
            train_ix = set(range(fold["train_start_idx"], fold["train_end_idx"]))
            test_ix = set(range(fold["test_start_idx"], fold["test_end_idx"]))
            assert not train_ix & test_ix

    def test_rolling_rejects_negative_embargo(self) -> None:
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        with pytest.raises(ValueError, match="embargo_days"):
            WalkForwardValidator(
                train_window_days=30,
                test_window_days=7,
                step_days=7,
                window_mode="rolling",
                embargo_days=-1,
            )


class TestWalkForwardValidatorFoldGeneration:
    """Test fold generation logic."""

    def test_folds_progress_through_time(self) -> None:
        """Each subsequent fold should be later in time."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = create_time_series_data(n_samples=3000)
        folds = validator.create_folds(df)

        for i in range(1, len(folds)):
            prev_test_start = folds[i - 1]["test_start"]
            curr_test_start = folds[i]["test_start"]

            assert curr_test_start > prev_test_start, (
                f"Fold {i} test_start ({curr_test_start}) should be after Fold {i - 1} test_start ({prev_test_start})"
            )

    def test_minimum_train_samples(self) -> None:
        """Folds with insufficient training data should be skipped."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
            min_train_samples=500,  # Require at least 500 samples
        )

        # Short dataset that might not have enough training data
        df = create_time_series_data(n_samples=1000)
        folds = validator.create_folds(df)

        for fold in folds:
            train_size = fold["train_end_idx"] - fold["train_start_idx"]
            assert train_size >= 500, f"Fold has only {train_size} train samples"

    def test_coverage_of_data(self) -> None:
        """Test sets should cover most of the data (after initial training window)."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = create_time_series_data(n_samples=3000)
        folds = validator.create_folds(df)

        # Collect all test indices
        all_test_indices = set()
        for fold in folds:
            test_indices = range(fold["test_start_idx"], fold["test_end_idx"])
            all_test_indices.update(test_indices)

        # Should cover a significant portion of the data
        coverage = len(all_test_indices) / len(df)
        # Note: First train_window_days worth of data can't be tested
        assert coverage > 0.5, f"Test coverage is only {coverage:.1%}"


class TestWalkForwardValidatorEdgeCases:
    """Test edge cases and error handling."""

    def test_insufficient_data(self) -> None:
        """Should handle data too short for even one fold."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=60,
            test_window_days=14,
            step_days=7,
        )

        # Only 500 hours = ~21 days, not enough for 60+14 = 74 days
        df = create_time_series_data(n_samples=500)
        folds = validator.create_folds(df)

        # Should return empty list, not crash
        assert len(folds) == 0

    def test_empty_dataframe(self) -> None:
        """Should handle empty DataFrame."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = pl.DataFrame(
            {
                "timestamp": [],
                "feature_0": [],
                "target": [],
            }
        )

        folds = validator.create_folds(df)
        assert len(folds) == 0

    def test_missing_timestamp_column(self) -> None:
        """Should raise error if timestamp column is missing."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = pl.DataFrame(
            {
                "feature_0": [1, 2, 3],
                "target": [0, 1, -1],
            }
        )

        with pytest.raises(ValueError, match="timestamp"):
            validator.create_folds(df)


class TestWalkForwardValidatorWithTrainer:
    """Integration tests with trainer."""

    def test_validate_returns_fold_results(self) -> None:
        """Validate method should return results for each fold."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = create_time_series_data(n_samples=2000)
        feature_cols = [c for c in df.columns if c.startswith("feature_")]

        # Mock trainer that returns a simple model
        class MockTrainer:
            def train(self, X, y):
                from unittest.mock import MagicMock

                model = MagicMock()
                model.predict = lambda x: np.zeros(len(x))
                return model

        trainer = MockTrainer()
        results = validator.validate(trainer, df, feature_cols)

        assert len(results) > 0
        for result in results:
            # FoldResult is a dataclass, not a dict
            assert hasattr(result, "fold_idx")
            assert hasattr(result, "train_size")
            assert hasattr(result, "test_size")
            assert hasattr(result, "metrics")
            # Also verify to_dict() works
            result_dict = result.to_dict()
            assert "fold_idx" in result_dict

    def test_validate_aggregates_metrics(self) -> None:
        """Should aggregate metrics across all folds."""
        from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator

        validator = WalkForwardValidator(
            train_window_days=30,
            test_window_days=7,
            step_days=7,
        )

        df = create_time_series_data(n_samples=2000)
        feature_cols = [c for c in df.columns if c.startswith("feature_")]

        # Mock trainer
        class MockTrainer:
            def train(self, X, y):
                from unittest.mock import MagicMock

                model = MagicMock()
                model.predict = lambda x: np.zeros(len(x))
                return model

        trainer = MockTrainer()
        results = validator.validate(trainer, df, feature_cols)

        # Should be able to get aggregate stats
        stats = validator.get_aggregate_stats(results)

        assert "mean_accuracy" in stats or "avg_accuracy" in stats or "accuracy" in stats
