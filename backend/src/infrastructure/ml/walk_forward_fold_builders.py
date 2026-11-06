"""
Fold construction for walk-forward time-series validation.

Pure date-arithmetic functions extracted from
:mod:`walk_forward_validator` so that module can stay focused on the
validator orchestration (train + predict + aggregate).

Two strategies:

- :func:`build_anchored_folds` — training always starts at the first
  timestamp; the training window grows until each test slice; the test
  window advances by ``step_days``.
- :func:`build_rolling_folds` — fixed-length training window of
  ``train_window_days`` slides forward by ``step_days``. Optional
  ``embargo_days`` gaps train from test (de Prado style).

CRITICAL: train_end must always be <= test_start (plus embargo) to prevent
future-data leakage. Both builders enforce this via a guard that raises
:class:`ValueError` if the invariant is ever violated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

_TS_MODE_GTE = "gte"
_TS_MODE_LT = "lt"


class FoldInfo(BaseModel):
    """
    Information about a validation fold.

    WHY Pydantic:
    - Validates fold info at construction
    - Consistent with other ML infrastructure models
    """

    model_config = ConfigDict(from_attributes=True)

    fold_idx: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_start_idx: int
    train_end_idx: int
    test_start_idx: int
    test_end_idx: int

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary (preserves datetime for internal use).

        NOTE: This intentionally keeps datetime objects as-is (not isoformat)
        because the dict is used internally by the validator pipeline,
        not for JSON serialization.

        WHY NOT mode='json':
        - Internal code expects datetime objects, not strings
        - create_folds() returns these dicts for further processing
        - JSON serialization happens at API boundary, not here
        """
        return self.model_dump()


def find_timestamp_idx(
    timestamps: list[datetime],
    target: datetime,
    mode: str = _TS_MODE_GTE,
) -> int:
    """
    Find index of timestamp in sorted list.

    Args:
        timestamps: Sorted list of timestamps
        target: Target datetime
        mode: 'gte' for >= or 'lt' for <

    Returns:
        Index in list
    """
    for i, ts in enumerate(timestamps):
        if mode == _TS_MODE_GTE and ts >= target:
            return i
        if mode == _TS_MODE_LT and ts >= target:
            return i

    return len(timestamps)


def build_anchored_folds(
    timestamps: list[datetime],
    start_date: datetime,
    end_date: datetime,
    *,
    train_window_days: int,
    test_window_days: int,
    step_days: int,
    min_train_samples: int,
) -> list[dict[str, Any]]:
    """Expanding train from series start; test slices advance by ``step_days``."""
    total_days = (end_date - start_date).days
    min_days_required = train_window_days + test_window_days
    if total_days < min_days_required:
        logger.warning(
            "Insufficient data: %d days available, need %d",
            total_days,
            min_days_required,
        )
        return []

    folds: list[dict[str, Any]] = []
    fold_idx = 0
    current_test_start = start_date + timedelta(days=train_window_days)

    while True:
        train_start = start_date
        train_end = current_test_start
        test_start = current_test_start
        test_end = test_start + timedelta(days=test_window_days)

        if test_end > end_date:
            break

        train_start_idx = find_timestamp_idx(timestamps, train_start, _TS_MODE_GTE)
        train_end_idx = find_timestamp_idx(timestamps, train_end, _TS_MODE_LT)
        test_start_idx = find_timestamp_idx(timestamps, test_start, _TS_MODE_GTE)
        test_end_idx = find_timestamp_idx(timestamps, test_end, _TS_MODE_LT)

        train_size = train_end_idx - train_start_idx
        if train_size < min_train_samples:
            logger.debug(
                "Skipping fold %d: only %d training samples (need %d)",
                fold_idx,
                train_size,
                min_train_samples,
            )
            current_test_start += timedelta(days=step_days)
            continue

        if train_end > test_start:
            raise ValueError(f"Future leak detected: train_end={train_end} > test_start={test_start}")

        fold = FoldInfo(
            fold_idx=fold_idx,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            train_start_idx=train_start_idx,
            train_end_idx=train_end_idx,
            test_start_idx=test_start_idx,
            test_end_idx=test_end_idx,
        )
        folds.append(fold.to_dict())
        logger.debug(
            "Fold %d: train=[%s to %s], test=[%s to %s]",
            fold_idx,
            train_start.strftime("%Y-%m-%d"),
            train_end.strftime("%Y-%m-%d"),
            test_start.strftime("%Y-%m-%d"),
            test_end.strftime("%Y-%m-%d"),
        )
        fold_idx += 1
        current_test_start += timedelta(days=step_days)

    return folds


def build_rolling_folds(
    timestamps: list[datetime],
    start_date: datetime,
    end_date: datetime,
    *,
    train_window_days: int,
    test_window_days: int,
    step_days: int,
    min_train_samples: int,
    embargo_days: int,
) -> list[dict[str, Any]]:
    """Fixed-length train window sliding by ``step_days``; optional embargo before test."""
    total_days = (end_date - start_date).days
    min_days_required = train_window_days + embargo_days + test_window_days
    if total_days < min_days_required:
        logger.warning(
            "Insufficient data: %d days available, need %d (train + embargo + test)",
            total_days,
            min_days_required,
        )
        return []

    folds: list[dict[str, Any]] = []
    fold_idx = 0
    current_train_start = start_date

    while True:
        train_start = current_train_start
        train_end = train_start + timedelta(days=train_window_days)
        test_start = train_end + timedelta(days=embargo_days)
        test_end = test_start + timedelta(days=test_window_days)

        if test_end > end_date:
            break

        train_start_idx = find_timestamp_idx(timestamps, train_start, _TS_MODE_GTE)
        train_end_idx = find_timestamp_idx(timestamps, train_end, _TS_MODE_LT)
        test_start_idx = find_timestamp_idx(timestamps, test_start, _TS_MODE_GTE)
        test_end_idx = find_timestamp_idx(timestamps, test_end, _TS_MODE_LT)

        train_size = train_end_idx - train_start_idx
        if train_size < min_train_samples:
            logger.debug(
                "Skipping rolling fold %d: only %d training samples (need %d)",
                fold_idx,
                train_size,
                min_train_samples,
            )
            current_train_start += timedelta(days=step_days)
            continue

        if train_end > test_start:
            raise ValueError(f"Future leak detected: train_end={train_end} > test_start={test_start}")

        fold = FoldInfo(
            fold_idx=fold_idx,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            train_start_idx=train_start_idx,
            train_end_idx=train_end_idx,
            test_start_idx=test_start_idx,
            test_end_idx=test_end_idx,
        )
        folds.append(fold.to_dict())
        logger.debug(
            "Rolling fold %d: train=[%s to %s], test=[%s to %s]",
            fold_idx,
            train_start.strftime("%Y-%m-%d"),
            train_end.strftime("%Y-%m-%d"),
            test_start.strftime("%Y-%m-%d"),
            test_end.strftime("%Y-%m-%d"),
        )
        fold_idx += 1
        current_train_start += timedelta(days=step_days)

    return folds
