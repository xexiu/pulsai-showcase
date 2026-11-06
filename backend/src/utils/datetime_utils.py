"""Backward-compatible re-export. Source of truth: ``src.shared.utils.datetime_utils``."""

from __future__ import annotations

from datetime import UTC

from src.shared.utils.datetime_utils import (
    ensure_utc,
    ensure_utc_pandas_index,
    normalize_timestamp_scalar_to_utc,
    parse_backtest_range_end_utc,
    parse_backtest_range_start_utc,
    parse_datetime_utc,
    polars_timestamp_to_epoch_ms,
    utc_now,
)

__all__ = [
    "UTC",
    "ensure_utc",
    "ensure_utc_pandas_index",
    "normalize_timestamp_scalar_to_utc",
    "parse_backtest_range_end_utc",
    "parse_backtest_range_start_utc",
    "parse_datetime_utc",
    "polars_timestamp_to_epoch_ms",
    "utc_now",
]
