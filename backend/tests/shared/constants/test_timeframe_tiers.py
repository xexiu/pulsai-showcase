"""Tests for subscription tier timeframe allowlists (SoT)."""

from src.shared.constants.timeframe_tiers import (
    TIMEFRAME_TIER_FREE,
    TIMEFRAME_TIER_PRO,
    TIMEFRAME_TIER_STARTER,
)
from src.shared.constants.timeframes import DEFAULT_SUPPORTED_TIMEFRAME_VALUES, TIMEFRAME_REGISTRY


class TestTimeframeTierAllowlists:
    def test_all_tier_values_exist_in_registry(self) -> None:
        registry = set(TIMEFRAME_REGISTRY.keys())
        for name, tier_set in (
            ("FREE", TIMEFRAME_TIER_FREE),
            ("STARTER", TIMEFRAME_TIER_STARTER),
            ("PRO", TIMEFRAME_TIER_PRO),
        ):
            unknown = tier_set - registry
            assert not unknown, f"{name} tier references unknown timeframes: {sorted(unknown)}"

    def test_tier_progression_is_monotonic(self) -> None:
        assert TIMEFRAME_TIER_FREE <= TIMEFRAME_TIER_STARTER <= TIMEFRAME_TIER_PRO

    def test_pro_includes_8h_and_12h(self) -> None:
        assert "8h" in TIMEFRAME_TIER_PRO
        assert "12h" in TIMEFRAME_TIER_PRO

    def test_pro_includes_3d(self) -> None:
        assert "3d" in TIMEFRAME_TIER_PRO

    def test_default_supported_subset_of_pro_tier(self) -> None:
        default_set = set(DEFAULT_SUPPORTED_TIMEFRAME_VALUES)
        assert default_set <= TIMEFRAME_TIER_PRO
