"""Tests for timeframe sort helpers (SoT: ``sort_timeframe_keys``)."""

from src.shared.constants.timeframes import sort_timeframe_keys


def test_sort_timeframe_keys_orders_by_duration() -> None:
    """WHEN given unsorted TFs THEN return ascending duration order."""
    assert sort_timeframe_keys(["1h", "5m", "15m"]) == ["5m", "15m", "1h"]


def test_sort_timeframe_keys_dedupes() -> None:
    """WHEN duplicates present THEN each TF appears once."""
    assert sort_timeframe_keys(["5m", "5m", "1h"]) == ["5m", "1h"]


def test_sort_timeframe_keys_unknown_tf_after_registry() -> None:
    """WHEN legacy TF not in registry THEN sort after known keys."""
    ordered = sort_timeframe_keys(["legacy_tf", "5m", "1w"])
    assert ordered.index("5m") < ordered.index("1w")
    assert ordered.index("1w") < ordered.index("legacy_tf")
