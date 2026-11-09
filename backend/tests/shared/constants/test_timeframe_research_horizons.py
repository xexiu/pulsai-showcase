"""Tests for research IC horizon grid (SoT)."""

from src.shared.constants.timeframe_research_horizons import IC_HORIZON_GRID_BY_TIMEFRAME
from src.shared.constants.timeframes import TIMEFRAME_MS, TIMEFRAME_REGISTRY, training_timeframes_ordered


class TestIcHorizonGrid:
    def test_all_keys_in_registry(self) -> None:
        unknown = set(IC_HORIZON_GRID_BY_TIMEFRAME.keys()) - set(TIMEFRAME_REGISTRY.keys())
        assert not unknown, f"IC grid has unknown registry keys: {sorted(unknown)}"

    def test_training_timeframes_have_horizons(self) -> None:
        for tf in training_timeframes_ordered():
            assert tf in IC_HORIZON_GRID_BY_TIMEFRAME, f"missing IC horizons for {tf!r}"
            horizons = IC_HORIZON_GRID_BY_TIMEFRAME[tf]
            assert len(horizons) >= 2
            assert all(h > 0 for h in horizons)

    def test_1m_grid_covers_the_same_wall_clock_horizons_as_5m(self) -> None:
        """1m (LTF since 2026-10-11) is DERIVED from 5m by bars-per-day scaling: 30 min / 1 h / 2 h."""
        one_minute_ms = [h * TIMEFRAME_MS["1m"] for h in IC_HORIZON_GRID_BY_TIMEFRAME["1m"]]
        five_minute_ms = [h * TIMEFRAME_MS["5m"] for h in IC_HORIZON_GRID_BY_TIMEFRAME["5m"]]

        assert one_minute_ms == five_minute_ms
