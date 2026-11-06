"""
Walk-Forward Validator

Time-series cross-validation that prevents future data leakage.
Implements rolling window validation for financial time-series.

CRITICAL: train_end must always be <= test_start to prevent future leak!

Sibling module:
- :mod:`walk_forward_fold_builders` — pure date-arithmetic builders for
  anchored / rolling folds, plus the FoldInfo Pydantic model. Re-exported
  below for backward compatibility.

@see docs/02-technical/ML_PIPELINE.md - Walk-Forward Validation
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal, Protocol

import numpy as np
import polars as pl
from pydantic import BaseModel, ConfigDict
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from src.infrastructure.ml.walk_forward_fold_builders import (
    FoldInfo,
    build_anchored_folds,
    build_rolling_folds,
)

logger = logging.getLogger(__name__)

__all__ = (
    "FoldInfo",
    "FoldResult",
    "Trainer",
    "WalkForwardValidator",
)


class Trainer(Protocol):
    """Protocol for trainers that can be used with WalkForwardValidator."""

    def train(self, X: np.ndarray, y: np.ndarray) -> Any:
        """Train and return a model with predict method."""
        ...


class FoldResult(BaseModel):
    """
    Results from evaluating a model on a fold.

    WHY Pydantic:
    - Validates fold results at construction
    - model_dump(mode='json') handles datetime → ISO string
    """

    model_config = ConfigDict(from_attributes=True)

    fold_idx: int
    train_size: int
    test_size: int
    metrics: dict[str, float]
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary with JSON-serializable values.

        Uses mode='json' to convert datetime → ISO string.
        """
        return self.model_dump(mode="json")


class WalkForwardValidator:
    """
    Walk-forward validation for time-series models.

    ``window_mode="anchored"`` (default): training always starts at the first timestamp;
    the training window grows until each test slice; the test window advances by ``step_days``.

    ``window_mode="rolling"``: fixed-length training window of ``train_window_days`` that
    slides forward by ``step_days`` after each fold (same geometry as
    ``application.services.walk_forward_folds.create_walk_forward_folds`` for hub
    re-optimization). Optional ``embargo_days`` gaps train from test (de Prado style).

    CRITICAL: No future data leakage — train period ends before the test period (plus embargo).

    Example:
        validator = WalkForwardValidator(
            train_window_days=60,
            test_window_days=14,
            step_days=7,
        )
        folds = validator.create_folds(df)
        results = validator.validate(trainer, df, feature_columns)
    """

    def __init__(
        self,
        train_window_days: int = 60,
        test_window_days: int = 14,
        step_days: int = 7,
        min_train_samples: int = 500,
        timestamp_col: str = "timestamp",
        *,
        window_mode: Literal["anchored", "rolling"] = "anchored",
        embargo_days: int = 0,
    ) -> None:
        """
        Initialize walk-forward validator.

        Args:
            train_window_days: Anchored: days before first test. Rolling: fixed train span (days).
            test_window_days: Test window size in days
            step_days: Step size between folds in days
            min_train_samples: Minimum samples required in training set
            timestamp_col: Name of timestamp column
            window_mode: ``anchored`` (expanding train) or ``rolling`` (sliding fixed train).
            embargo_days: Rolling only (ignored for anchored): gap in days after train before test.
        """
        if window_mode not in ("anchored", "rolling"):
            raise ValueError('window_mode must be "anchored" or "rolling"')
        if embargo_days < 0:
            raise ValueError("embargo_days must be non-negative")
        if window_mode == "anchored" and embargo_days != 0:
            logger.warning(
                "embargo_days=%s ignored for anchored window_mode (anchored folds use no embargo)",
                embargo_days,
            )
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.step_days = step_days
        self.min_train_samples = min_train_samples
        self.timestamp_col = timestamp_col
        self.window_mode: Literal["anchored", "rolling"] = window_mode
        self.embargo_days = embargo_days

    def create_folds(
        self,
        df: pl.DataFrame,
    ) -> list[dict[str, Any]]:
        """
        Create validation folds from time-series data.

        Args:
            df: Polars DataFrame with timestamp column

        Returns:
            List of fold dictionaries with date boundaries and indices

        Raises:
            ValueError: If timestamp column is missing
        """
        if self.timestamp_col not in df.columns:
            msg = f"DataFrame must have '{self.timestamp_col}' column"
            raise ValueError(msg)

        if len(df) == 0:
            return []

        df_sorted = df.sort(self.timestamp_col)
        timestamps = df_sorted[self.timestamp_col].to_list()
        start_date = timestamps[0]
        end_date = timestamps[-1]

        if self.window_mode == "rolling":
            folds = build_rolling_folds(
                timestamps,
                start_date,
                end_date,
                train_window_days=self.train_window_days,
                test_window_days=self.test_window_days,
                step_days=self.step_days,
                min_train_samples=self.min_train_samples,
                embargo_days=self.embargo_days,
            )
        else:
            folds = build_anchored_folds(
                timestamps,
                start_date,
                end_date,
                train_window_days=self.train_window_days,
                test_window_days=self.test_window_days,
                step_days=self.step_days,
                min_train_samples=self.min_train_samples,
            )

        logger.info("Created %d validation folds (%s)", len(folds), self.window_mode)
        return folds

    def validate(
        self,
        trainer: Trainer,
        df: pl.DataFrame,
        feature_columns: list[str],
        target_col: str = "target",
    ) -> list[FoldResult]:
        """
        Run walk-forward validation with a trainer.

        Args:
            trainer: Trainer with train(X, y) method returning model
            df: DataFrame with features and target
            feature_columns: List of feature column names
            target_col: Name of target column

        Returns:
            List of FoldResult for each fold
        """
        folds = self.create_folds(df)

        if len(folds) == 0:
            logger.warning("No folds created, returning empty results")
            return []

        results = []
        df_sorted = df.sort(self.timestamp_col)

        for fold in folds:
            # Extract train/test data
            train_df = df_sorted[fold["train_start_idx"] : fold["train_end_idx"]]
            test_df = df_sorted[fold["test_start_idx"] : fold["test_end_idx"]]

            # Get X, y
            X_train = train_df.select(feature_columns).to_numpy()
            y_train = train_df[target_col].to_numpy()
            X_test = test_df.select(feature_columns).to_numpy()
            y_test = test_df[target_col].to_numpy()

            # Handle NaN in target (rows without valid targets)
            valid_train_mask = ~np.isnan(y_train)
            valid_test_mask = ~np.isnan(y_test)

            X_train = X_train[valid_train_mask]
            y_train = y_train[valid_train_mask]
            X_test = X_test[valid_test_mask]
            y_test = y_test[valid_test_mask]

            if len(X_train) == 0 or len(X_test) == 0:
                logger.warning("Fold %d: empty train or test set after NaN removal", fold["fold_idx"])
                continue

            # Train model
            try:
                model = trainer.train(X_train, y_train)
            except Exception as e:
                logger.exception("Fold %d training failed: %s", fold["fold_idx"], e)
                continue

            # Predict
            y_pred = model.predict(X_test)

            # Calculate metrics
            metrics = self._calculate_metrics(y_test, y_pred)

            result = FoldResult(
                fold_idx=fold["fold_idx"],
                train_size=len(X_train),
                test_size=len(X_test),
                metrics=metrics,
                train_start=fold["train_start"],
                train_end=fold["train_end"],
                test_start=fold["test_start"],
                test_end=fold["test_end"],
            )

            results.append(result)

            logger.info(
                "Fold %d: accuracy=%.3f, f1=%.3f (train=%d, test=%d)",
                fold["fold_idx"],
                metrics["accuracy"],
                metrics["f1_weighted"],
                len(X_train),
                len(X_test),
            )

        return results

    def get_aggregate_stats(
        self,
        results: list[FoldResult],
    ) -> dict[str, float]:
        """
        Calculate aggregate statistics across all folds.

        Args:
            results: List of FoldResult from validate()

        Returns:
            Dictionary with mean/std of metrics
        """
        if len(results) == 0:
            return {}

        # Collect metrics
        accuracies = [r.metrics["accuracy"] for r in results]
        f1_scores = [r.metrics["f1_weighted"] for r in results]
        precisions = [r.metrics["precision_weighted"] for r in results]
        recalls = [r.metrics["recall_weighted"] for r in results]

        return {
            "n_folds": len(results),
            "mean_accuracy": float(np.mean(accuracies)),
            "std_accuracy": float(np.std(accuracies)),
            "mean_f1": float(np.mean(f1_scores)),
            "std_f1": float(np.std(f1_scores)),
            "mean_precision": float(np.mean(precisions)),
            "mean_recall": float(np.mean(recalls)),
            "accuracy": float(np.mean(accuracies)),  # Alias for tests
        }

    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> dict[str, float]:
        """Calculate classification metrics."""
        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division="warn")),
            "precision_weighted": float(precision_score(y_true, y_pred, average="weighted", zero_division="warn")),
            "recall_weighted": float(recall_score(y_true, y_pred, average="weighted", zero_division="warn")),
        }
