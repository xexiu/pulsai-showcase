"""Tests for public config timeframe metadata (SoT)."""

from src.shared.constants.timeframes import (
    TIMEFRAME_LABELS,
    TIMEFRAME_REGISTRY,
    build_public_timeframe_options,
)


class TestBuildPublicTimeframeOptions:
    def test_each_option_has_registry_ms_and_label(self) -> None:
        supported = ["5m", "1h", "4h", "8h", "12h"]
        options = build_public_timeframe_options(supported)
        assert [o.value for o in options] == supported
        for opt in options:
            assert opt.ms == TIMEFRAME_REGISTRY[opt.value].milliseconds
            assert opt.label == TIMEFRAME_LABELS[opt.value]

    def test_sorted_by_duration_ascending(self) -> None:
        supported = ["1d", "5m", "4h", "1h"]
        options = build_public_timeframe_options(supported)
        assert [o.value for o in options] == ["5m", "1h", "4h", "1d"]

    def test_unknown_values_skipped(self) -> None:
        options = build_public_timeframe_options(["1h", "not-a-timeframe", "4h"])
        assert [o.value for o in options] == ["1h", "4h"]
