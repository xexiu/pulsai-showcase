"""Behavior tests for OOSPredictionCollector (meta-labeling Slice 1b).

The collector produces the primary model's OUT-OF-SAMPLE predictions via
walk-forward folds, so the meta-labels built from them are leak-free
(anti-circularity). It reuses WalkForwardValidator.create_folds() for the
leak-safe fold boundaries and runs train→predict→stitch per fold.

The load-bearing tests are the anti-circularity ones: a stub model records which
row ids it was trained on and predicts "was I trained on this row?"; every covered
OOS prediction must be 0 — including under OVERLAPPING test windows (last-write-wins).

@see docs/02-technical/META_LABELING_PLAN.md (Slice 1b)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from src.infrastructure.ml.meta_labeling.oos_prediction_collector import OOSPredictionCollector
from src.infrastructure.ml.walk_forward_validator import WalkForwardValidator


def _frame(n: int = 20) -> pl.DataFrame:
    """Daily bars with a `row_id` feature == row index and a valid target."""
    base = datetime(2026, 1, 1)
    return pl.DataFrame(
        {
            "timestamp": [base + timedelta(days=i) for i in range(n)],
            "row_id": [float(i) for i in range(n)],
            "row_id_x10": [float(i) * 10.0 for i in range(n)],
            "target": [1.0] * n,  # non-NaN so per-fold training proceeds
        }
    )


def _validator() -> WalkForwardValidator:
    # Small rolling windows + 1-day embargo; step == test_window → adjacent (non-overlapping).
    return WalkForwardValidator(
        train_window_days=4,
        test_window_days=2,
        step_days=2,
        min_train_samples=1,
        window_mode="rolling",
        embargo_days=1,
    )


def _overlapping_validator() -> WalkForwardValidator:
    # step (1) < test_window (4) → test windows OVERLAP, exercising last-write-wins.
    return WalkForwardValidator(
        train_window_days=5,
        test_window_days=4,
        step_days=1,
        min_train_samples=1,
        window_mode="rolling",
        embargo_days=0,
    )


class _EchoModel:
    """Predicts a chosen feature column — used to verify index/column alignment."""

    def __init__(self, col: int = 0) -> None:
        self._col = col

    def predict(self, x: np.ndarray) -> np.ndarray:
        return x[:, self._col]


class _EchoTrainer:
    def __init__(self, col: int = 0) -> None:
        self._col = col

    def train(self, x: np.ndarray, y: np.ndarray) -> _EchoModel:
        return _EchoModel(self._col)


class _MembershipModel:
    """Predicts 1.0 if a row was in this model's training set, else 0.0."""

    def __init__(self, train_ids: set[float]) -> None:
        self._train_ids = train_ids

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.array([1.0 if rid in self._train_ids else 0.0 for rid in x[:, 0]])


class _MembershipTrainer:
    def train(self, x: np.ndarray, y: np.ndarray) -> _MembershipModel:
        return _MembershipModel(set(x[:, 0].tolist()))


class TestOOSPredictionCollectorCoverage:
    def test_pre_test_and_embargo_bars_are_uncovered(self) -> None:
        result = OOSPredictionCollector(_validator()).collect(_EchoTrainer(), _frame(20), feature_columns=["row_id"], target_col="target")

        # Bars 0..4 are training-only / embargo (never in a test window) → uncovered
        assert not result.coverage_mask[:5].any()
        assert result.coverage_mask[5:].any()
        assert result.n_covered == int(result.coverage_mask.sum())
        assert result.n_folds >= 1

    def test_empty_frame_yields_no_predictions(self) -> None:
        result = OOSPredictionCollector(_validator()).collect(_EchoTrainer(), _frame(0), feature_columns=["row_id"], target_col="target")

        assert result.predictions.shape[0] == 0
        assert result.n_folds == 0
        assert result.n_covered == 0

    def test_fold_with_all_nan_train_targets_is_skipped(self) -> None:
        # Bars 0..3 (fold 0's train window) have NaN targets → fold 0 is skipped, so its
        # test bars (5,6) get no prediction; later folds (valid targets) still cover bars 7+.
        frame = _frame(20).with_columns(pl.when(pl.col("row_id") < 4).then(None).otherwise(pl.col("target")).alias("target"))
        result = OOSPredictionCollector(_validator()).collect(_EchoTrainer(), frame, feature_columns=["row_id"], target_col="target")

        assert not result.coverage_mask[5:7].any()  # fold 0 skipped
        assert result.coverage_mask[7:].any()  # later folds still produce predictions


class TestOOSPredictionCollectorAlignment:
    def test_oos_predictions_align_to_their_bar_index(self) -> None:
        result = OOSPredictionCollector(_validator()).collect(_EchoTrainer(), _frame(20), feature_columns=["row_id"], target_col="target")

        row_id = _frame(20)["row_id"].to_numpy()
        covered = np.where(result.coverage_mask)[0]
        assert covered.size > 0
        for idx in covered:
            assert result.predictions[idx] == row_id[idx]

    def test_unsorted_input_is_realigned_to_original_rows(self) -> None:
        # Reversed (descending-timestamp) frame: the collector sorts internally and must
        # scatter predictions back so predictions[i] still matches that input row's feature.
        frame = _frame(20).reverse()
        result = OOSPredictionCollector(_validator()).collect(_EchoTrainer(), frame, feature_columns=["row_id"], target_col="target")

        row_id = frame["row_id"].to_numpy()
        covered = np.where(result.coverage_mask)[0]
        assert covered.size > 0
        for idx in covered:
            assert result.predictions[idx] == row_id[idx]

    def test_multiple_feature_columns_are_passed_in_order(self) -> None:
        # Echo the SECOND feature (row_id_x10): proves columns reach the model in order.
        result = OOSPredictionCollector(_validator()).collect(
            _EchoTrainer(col=1), _frame(20), feature_columns=["row_id", "row_id_x10"], target_col="target"
        )

        expected = _frame(20)["row_id_x10"].to_numpy()
        covered = np.where(result.coverage_mask)[0]
        assert covered.size > 0
        for idx in covered:
            assert result.predictions[idx] == expected[idx]


class TestOOSPredictionCollectorAntiCircularity:
    def test_no_test_bar_leaks_into_its_training_set(self) -> None:
        result = OOSPredictionCollector(_validator()).collect(_MembershipTrainer(), _frame(20), feature_columns=["row_id"], target_col="target")

        covered = result.predictions[result.coverage_mask]
        assert covered.size > 0
        assert np.all(covered == 0.0), "a covered bar was trained on by its own predicting model (leak!)"

    def test_overlapping_test_windows_stay_leak_free(self) -> None:
        # step < test_window → overlapping test windows + last-write-wins. Still leak-free:
        # the latest fold writing a bar has train_end <= test_start <= that bar.
        result = OOSPredictionCollector(_overlapping_validator()).collect(
            _MembershipTrainer(), _frame(20), feature_columns=["row_id"], target_col="target"
        )

        covered = result.predictions[result.coverage_mask]
        assert covered.size > 0
        assert result.n_folds >= 2  # overlapping config produces many folds
        assert np.all(covered == 0.0), "overlapping last-write-wins leaked a training bar into its own prediction"


class TestOOSPredictionCollectorValidation:
    def test_duplicate_timestamps_are_rejected(self) -> None:
        frame = _frame(20).with_columns(pl.lit(datetime(2026, 1, 1)).alias("timestamp"))
        with pytest.raises(ValueError, match="unique"):
            OOSPredictionCollector(_validator()).collect(_EchoTrainer(), frame, feature_columns=["row_id"], target_col="target")

    def test_null_timestamps_are_rejected(self) -> None:
        frame = _frame(20).with_columns(pl.when(pl.col("row_id") == 0).then(None).otherwise(pl.col("timestamp")).alias("timestamp"))
        with pytest.raises(ValueError, match="null"):
            OOSPredictionCollector(_validator()).collect(_EchoTrainer(), frame, feature_columns=["row_id"], target_col="target")
