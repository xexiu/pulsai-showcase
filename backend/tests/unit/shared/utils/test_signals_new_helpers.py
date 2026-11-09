"""Behavior tests for the two new signal helpers added to shared/utils/signals.py.

RED phase: written before implementation; ensures the helpers behave according
to the API contract defined in the task specification.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.domain.enums import SignalAction
from src.shared.utils.signals import (
    API_SIGNAL_BUY,
    API_SIGNAL_HOLD,
    API_SIGNAL_SELL,
    is_regression_model_type,
    signal_action_to_api_int,
    signal_from_cuts,
)


class TestIsRegressionModelType:
    """is_regression_model_type(model_type) -> bool."""

    def test_returns_true_for_lowercase_regression(self) -> None:
        assert is_regression_model_type("regression") is True

    def test_returns_true_for_xgboost_regression(self) -> None:
        assert is_regression_model_type("xgboost_regression") is True

    def test_returns_true_for_uppercase(self) -> None:
        assert is_regression_model_type("REGRESSION") is True

    def test_returns_true_for_mixed_case(self) -> None:
        assert is_regression_model_type("XGBoost_Regression_v2") is True

    def test_returns_false_for_3class(self) -> None:
        assert is_regression_model_type("xgboost_3class") is False

    def test_returns_false_for_2class_buy(self) -> None:
        assert is_regression_model_type("xgboost_2class_buy") is False

    def test_returns_false_for_none(self) -> None:
        assert is_regression_model_type(None) is False

    def test_returns_false_for_empty_string(self) -> None:
        assert is_regression_model_type("") is False

    def test_returns_true_when_regression_is_substring(self) -> None:
        """'regression' anywhere in the string → True."""
        assert is_regression_model_type("lgbm_regression_quantile") is True


class TestSignalActionToApiInt:
    """signal_action_to_api_int(action) -> int using canonical API_SIGNAL_* constants."""

    def test_buy_maps_to_api_signal_buy(self) -> None:
        result = signal_action_to_api_int(SignalAction.BUY)
        assert result == API_SIGNAL_BUY
        assert result == 1

    def test_sell_maps_to_api_signal_sell(self) -> None:
        result = signal_action_to_api_int(SignalAction.SELL)
        assert result == API_SIGNAL_SELL
        assert result == -1

    def test_hold_maps_to_api_signal_hold(self) -> None:
        result = signal_action_to_api_int(SignalAction.HOLD)
        assert result == API_SIGNAL_HOLD
        assert result == 0

    def test_return_type_is_int(self) -> None:
        assert isinstance(signal_action_to_api_int(SignalAction.BUY), int)
        assert isinstance(signal_action_to_api_int(SignalAction.SELL), int)
        assert isinstance(signal_action_to_api_int(SignalAction.HOLD), int)

    @pytest.mark.parametrize(
        ("action", "expected"),
        [
            (SignalAction.BUY, 1),
            (SignalAction.SELL, -1),
            (SignalAction.HOLD, 0),
        ],
    )
    def test_parametrized_all_actions(self, action: SignalAction, expected: int) -> None:
        assert signal_action_to_api_int(action) == expected


class TestSignalFromCuts:
    """signal_from_cuts(score, low, high): BUY at or above high, SELL at or below low, HOLD between."""

    def test_a_score_on_a_cut_takes_that_side(self) -> None:
        score = np.array([0.1, 0.3, 0.5, 0.7, 0.9])

        assert signal_from_cuts(score, 0.3, 0.7).tolist() == [API_SIGNAL_SELL, API_SIGNAL_SELL, API_SIGNAL_HOLD, API_SIGNAL_BUY, API_SIGNAL_BUY]

    def test_crossed_cuts_give_buy_its_precedence(self) -> None:
        # low above high (a quantile pair taken the other way round): the old copies' nested where tested high first
        assert signal_from_cuts(np.array([0.0, 0.5, 1.0]), 0.6, 0.4).tolist() == [API_SIGNAL_SELL, API_SIGNAL_BUY, API_SIGNAL_BUY]

    def test_a_missing_score_holds(self) -> None:
        assert signal_from_cuts(np.array([np.nan]), 0.3, 0.7).tolist() == [API_SIGNAL_HOLD]

    def test_per_bar_cuts_trade_ties_and_a_missing_cut_holds(self) -> None:
        # the z12 rolling book's case: one cut pair per bar, NaN where no model is fitted yet
        score = np.array([0.5, 0.49, -0.5, -0.49, np.nan, 0.7])
        high = np.array([0.5, 0.5, 0.5, 0.5, 0.5, np.nan])

        assert signal_from_cuts(score, -high, high).tolist() == [1, 0, -1, 0, 0, 0]
