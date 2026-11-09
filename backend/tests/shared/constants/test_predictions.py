"""
TDD tests for prediction class constants (Phase 2 §13 #6).

Constant values must match model output contract: 0=SELL, 1=HOLD, 2=BUY.
Signal mapping: 0 -> -1, 1 -> 0, 2 -> 1 (trainer_metrics, convert_predictions_to_signals).
"""

import numpy as np

import src.shared.constants.predictions as pred_consts
from src.shared.constants import (
    PREDICTION_CLASS_BUY,
    PREDICTION_CLASS_HOLD,
    PREDICTION_CLASS_SELL,
)
from src.shared.utils.signals import (
    CLASS_IDX_TO_ACTION_STR,
    PREDICTION_TO_SIGNAL_3CLASS,
    convert_predictions_to_signals,
)


class TestPredictionClassConstantValues:
    """Constant values match 3-class model contract (0=SELL, 1=HOLD, 2=BUY)."""

    def test_prediction_class_sell_is_zero(self) -> None:
        """PREDICTION_CLASS_SELL must be 0 (model output for SELL)."""
        assert PREDICTION_CLASS_SELL == 0

    def test_prediction_class_hold_is_one(self) -> None:
        """PREDICTION_CLASS_HOLD must be 1 (model output for HOLD)."""
        assert PREDICTION_CLASS_HOLD == 1

    def test_prediction_class_buy_is_two(self) -> None:
        """PREDICTION_CLASS_BUY must be 2 (model output for BUY)."""
        assert PREDICTION_CLASS_BUY == 2

    def test_constants_match_model_output_contract(self) -> None:
        """Signal map 0->-1, 1->0, 2->1 (same as trainer_metrics and backtester)."""
        expected = {
            PREDICTION_CLASS_SELL: -1,
            PREDICTION_CLASS_HOLD: 0,
            PREDICTION_CLASS_BUY: 1,
        }
        assert expected == PREDICTION_TO_SIGNAL_3CLASS

    def test_convert_predictions_to_signals_uses_constants(self) -> None:
        """convert_predictions_to_signals maps 0/1/2 to -1/0/1 (behavior)."""
        predictions = np.array(
            [PREDICTION_CLASS_SELL, PREDICTION_CLASS_HOLD, PREDICTION_CLASS_BUY],
            dtype=np.int32,
        )
        signals = convert_predictions_to_signals(predictions)
        expected = np.array([-1, 0, 1], dtype=np.int32)
        np.testing.assert_array_equal(signals, expected)

    def test_class_idx_to_action_str_keys_match_prediction_constants(self) -> None:
        """Regression: CLASS_IDX_TO_ACTION_STR numeric keys must match SoT constants (no drift)."""
        assert CLASS_IDX_TO_ACTION_STR[PREDICTION_CLASS_SELL]
        assert CLASS_IDX_TO_ACTION_STR[PREDICTION_CLASS_HOLD]
        assert CLASS_IDX_TO_ACTION_STR[PREDICTION_CLASS_BUY]
        assert 0 in CLASS_IDX_TO_ACTION_STR
        assert 1 in CLASS_IDX_TO_ACTION_STR
        assert 2 in CLASS_IDX_TO_ACTION_STR


class TestPredictionConstantsExported:
    """Prediction constants are exported from shared.constants."""

    def test_prediction_class_sell_exported(self) -> None:
        """PREDICTION_CLASS_SELL is importable from shared.constants."""
        import src.shared.constants as sc

        assert hasattr(sc, "PREDICTION_CLASS_SELL")
        assert sc.PREDICTION_CLASS_SELL == pred_consts.PREDICTION_CLASS_SELL

    def test_prediction_class_hold_exported(self) -> None:
        """PREDICTION_CLASS_HOLD is importable from shared.constants."""
        import src.shared.constants as sc

        assert hasattr(sc, "PREDICTION_CLASS_HOLD")
        assert sc.PREDICTION_CLASS_HOLD == pred_consts.PREDICTION_CLASS_HOLD

    def test_prediction_class_buy_exported(self) -> None:
        """PREDICTION_CLASS_BUY is importable from shared.constants."""
        import src.shared.constants as sc

        assert hasattr(sc, "PREDICTION_CLASS_BUY")
        assert sc.PREDICTION_CLASS_BUY == pred_consts.PREDICTION_CLASS_BUY
