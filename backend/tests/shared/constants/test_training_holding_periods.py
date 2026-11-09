"""Tests for holding-period research grid SoT."""

import pytest

from src.infrastructure.config.training import TRAINING_TIMEFRAME_POLICIES, get_training_timeframe_policy
from src.shared.constants.cv_defaults import DEFAULT_HOLDING_PERIODS
from src.shared.constants.timeframes import VALID_TIMEFRAMES_SIGNAL_AND_TRAINING
from src.shared.constants.training_holding_periods import (
    HOLDING_PERIOD_RESEARCH_GRID,
    HOLDING_PERIOD_RESEARCH_GRID_MAX,
)


class TestHoldingPeriodResearchGrid:
    def test_grid_starts_at_default_and_caps_at_max(self) -> None:
        assert HOLDING_PERIOD_RESEARCH_GRID[0] == DEFAULT_HOLDING_PERIODS
        assert max(HOLDING_PERIOD_RESEARCH_GRID) == HOLDING_PERIOD_RESEARCH_GRID_MAX

    def test_grid_is_strictly_increasing(self) -> None:
        assert list(HOLDING_PERIOD_RESEARCH_GRID) == sorted(HOLDING_PERIOD_RESEARCH_GRID)
        assert len(set(HOLDING_PERIOD_RESEARCH_GRID)) == len(HOLDING_PERIOD_RESEARCH_GRID)


class TestTrainingPoliciesArePerTimeframe:
    def test_5m_uses_longer_label_horizon_than_1h(self) -> None:
        assert get_training_timeframe_policy("5m").holding_periods > get_training_timeframe_policy("1h").holding_periods

    def test_1h_default_matches_cv_sot(self) -> None:
        assert TRAINING_TIMEFRAME_POLICIES["1h"].holding_periods == DEFAULT_HOLDING_PERIODS


class TestRegressionHoldingPeriodsByTimeframe:
    """Continuous regression targets scale wall-clock horizon into bars per TF."""

    def test_4h_matches_nonprice_vol_research_horizon(self) -> None:
        from src.infrastructure.config.training import get_regression_holding_periods

        assert get_regression_holding_periods("4h") == 6

    def test_1d_matches_nonprice_range_research_horizon(self) -> None:
        from src.infrastructure.config.training import get_regression_holding_periods

        assert get_regression_holding_periods("1d") == 1

    def test_5m_uses_more_bars_than_1h_for_same_wall_clock(self) -> None:
        from src.infrastructure.config.training import get_regression_holding_periods

        assert get_regression_holding_periods("5m") > get_regression_holding_periods("1h")

    def test_1h_regression_horizon_is_24_bars(self) -> None:
        from src.infrastructure.config.training import get_regression_holding_periods

        assert get_regression_holding_periods("1h") == 24

    def test_1m_regression_horizon_is_one_day_of_minute_bars(self) -> None:
        """The table's own wall-clock rule (REGRESSION_TARGET_FORWARD_HOURS = 24h), not a 1m special case."""
        from src.infrastructure.config.training import get_regression_holding_periods

        assert get_regression_holding_periods("1m") == 1440

    @pytest.mark.parametrize("tf", sorted(VALID_TIMEFRAMES_SIGNAL_AND_TRAINING))
    def test_every_training_timeframe_has_regression_horizon(self, tf: str) -> None:
        from src.infrastructure.config.training import get_regression_holding_periods

        assert get_regression_holding_periods(tf) >= 1
