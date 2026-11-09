"""Out-of-sample prediction collection for meta-labeling (Slice 1b).

Produces the primary model's OUT-OF-SAMPLE predictions across walk-forward folds.
Feeding these (rather than in-sample predictions) into the meta-label builder is
the anti-circularity guarantee: a bar's prediction always comes from a model
trained strictly before that bar (the leak-safe fold boundaries are enforced by
WalkForwardValidator.create_folds — train_end <= test_start, plus embargo).

This collector REUSES create_folds() for the boundaries and runs the
train→predict→stitch loop itself, leaving the shared validator untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import polars as pl

    from src.infrastructure.ml.walk_forward_validator import Trainer, WalkForwardValidator

# Transient column holding each row's original position, so predictions computed in
# timestamp-sorted order can be scattered back to the caller's row order.
_ORIG_POS_COL = "__oos_orig_pos__"


@dataclass(frozen=True)
class OOSPredictions:
    """Out-of-sample predictions aligned 1:1 with the caller's input rows.

    `predictions[i]` is NaN where bar i was never in a test window (the initial
    train-only region and embargo gaps); `coverage_mask` marks the populated bars.
    NaN is the "uncovered" sentinel — a model that itself emits NaN predictions
    would be indistinguishable from an uncovered bar (not a concern for the binary
    primary classifiers this feeds).
    """

    predictions: np.ndarray  # float, NaN where uncovered
    coverage_mask: np.ndarray  # bool
    n_folds: int  # folds that produced predictions
    n_covered: int  # bars with an OOS prediction


class OOSPredictionCollector:
    """Collects leak-safe out-of-sample predictions via walk-forward folds."""

    def __init__(self, validator: WalkForwardValidator) -> None:
        self.validator = validator

    def collect(
        self,
        trainer: Trainer,
        df: pl.DataFrame,
        feature_columns: list[str],
        target_col: str = "target",
    ) -> OOSPredictions:
        """Train per fold and stitch each fold's test-window predictions into one array.

        Args:
            trainer: trains on (X, y) and returns a model exposing predict(X). The
                model must return one prediction per row and handle the feature
                values as given (no per-fold error swallowing — a failing fold
                raises, surfacing the problem rather than silently shrinking coverage).
            df: features + a timestamp column with UNIQUE, non-null values (the OHLCV
                single-writer invariant). Need not be pre-sorted — it is sorted
                internally and predictions are scattered back to input-row order.
            feature_columns: model input columns.
            target_col: training target column (NaN rows are dropped from TRAINING
                only; every test-window bar still receives a prediction).

        Raises:
            ValueError: if the timestamp column is missing, contains nulls, or has
                duplicate values (which would make row alignment ambiguous).
        """
        n = df.height
        predictions = np.full(n, np.nan, dtype=float)
        if n == 0:
            return OOSPredictions(predictions=predictions, coverage_mask=np.zeros(0, dtype=bool), n_folds=0, n_covered=0)

        timestamp_col = self.validator.timestamp_col
        self._validate_timestamps(df, timestamp_col, n)

        # Sort with an explicit original-position column. We slice THIS sorted frame
        # (not the caller's df), so fold indices and rows share one ordering — and
        # unique timestamps make that ordering deterministic (no tie ambiguity).
        df_sorted = df.with_row_index(_ORIG_POS_COL).sort(timestamp_col)
        orig_pos = df_sorted[_ORIG_POS_COL].to_numpy()

        folds = self.validator.create_folds(df_sorted)
        sorted_preds = np.full(n, np.nan, dtype=float)
        n_folds_used = 0
        for fold in folds:
            train_df = df_sorted[fold["train_start_idx"] : fold["train_end_idx"]]
            x_train = train_df.select(feature_columns).to_numpy()
            y_train = train_df[target_col].to_numpy()

            valid_train = ~np.isnan(y_train)
            x_train = x_train[valid_train]
            y_train = y_train[valid_train]
            if x_train.shape[0] == 0:
                continue  # no trainable rows in this fold's window

            test_start, test_end = fold["test_start_idx"], fold["test_end_idx"]
            x_test = df_sorted[test_start:test_end].select(feature_columns).to_numpy()
            if x_test.shape[0] == 0:
                continue

            model = trainer.train(x_train, y_train)
            # Later (more recent) folds overwrite on overlap — mimics production
            # retraining cadence, and stays leak-free since train_end <= test_start.
            sorted_preds[test_start:test_end] = model.predict(x_test)
            n_folds_used += 1

        # Scatter back to the caller's original row order.
        predictions[orig_pos] = sorted_preds
        coverage_mask = ~np.isnan(predictions)
        return OOSPredictions(
            predictions=predictions,
            coverage_mask=coverage_mask,
            n_folds=n_folds_used,
            n_covered=int(coverage_mask.sum()),
        )

    @staticmethod
    def _validate_timestamps(df: pl.DataFrame, timestamp_col: str, n: int) -> None:
        """Reject inputs that would make row↔prediction alignment ambiguous."""
        if timestamp_col not in df.columns:
            msg = f"df must have a '{timestamp_col}' column"
            raise ValueError(msg)
        series = df[timestamp_col]
        if series.null_count() > 0:
            msg = f"df '{timestamp_col}' must not contain nulls"
            raise ValueError(msg)
        if series.n_unique() != n:
            msg = f"df '{timestamp_col}' must be unique (OHLCV single-writer invariant) so OOS predictions align to bars"
            raise ValueError(msg)
