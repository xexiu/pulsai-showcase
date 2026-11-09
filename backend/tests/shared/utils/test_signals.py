"""
TDD Tests for signal conversion utilities.

Signal conversion is CRITICAL for correct trading behavior.

The mapping depends on the MODEL TYPE:

## 3-class model (model_direction=None):
- Predictions: 0=SELL, 1=HOLD, 2=BUY
- Signals: -1=SHORT, 0=HOLD, 1=LONG
- Formula: predictions - 1 = signals

## 2-class BUY model (model_direction="buy"):
- Predictions: 0=NOT-BUY, 1=BUY
- Signals: 0=HOLD, 1=LONG
- No transformation (same values)

## 2-class SELL model (model_direction="sell"):
- Predictions: 0=NOT-SELL, 1=SELL
- Signals: 0=HOLD, -1=SHORT
- Formula: 1→-1, 0→0

@see Plan Phase 2.3 - 7 occurrences across backtester.py, validation.py, etc.
@see src.workers.tasks.training_tasks_job.infer_model_direction
"""

import numpy as np

from src.domain.enums import SignalAction
from src.shared.utils.signals import (
    API_SIGNAL_BUY,
    API_SIGNAL_HOLD,
    API_SIGNAL_SELL,
    API_SIGNAL_TO_ACTION,
    API_SIGNAL_VALUES,
    PREDICTION_TO_SIGNAL_3CLASS,
    SIGNAL_TO_PREDICTION_3CLASS,
    convert_predictions_to_signals,
    convert_signals_to_predictions,
    resolve_model_direction,
)


class TestApiSignalConstants:
    """SoT: API signal constants used by response builders and regression converter."""

    def test_api_signal_values_match_contract(self) -> None:
        """API space is (-1, 0, 1) for 3-class, 2-class, and regression."""
        assert API_SIGNAL_SELL == -1
        assert API_SIGNAL_HOLD == 0
        assert API_SIGNAL_BUY == 1
        assert API_SIGNAL_VALUES == (API_SIGNAL_SELL, API_SIGNAL_HOLD, API_SIGNAL_BUY)

    def test_api_signal_to_action_matches_domain_enum(self) -> None:
        """API_SIGNAL_TO_ACTION must match SignalAction enum (no hardcoded dicts elsewhere)."""
        assert API_SIGNAL_TO_ACTION[API_SIGNAL_SELL] == SignalAction.SELL.value
        assert API_SIGNAL_TO_ACTION[API_SIGNAL_HOLD] == SignalAction.HOLD.value
        assert API_SIGNAL_TO_ACTION[API_SIGNAL_BUY] == SignalAction.BUY.value
        assert len(API_SIGNAL_TO_ACTION) == 3


class TestResolveModelDirection:
    """SoT resolver: prefer persisted model_direction, fall back to model_type string.

    WHY this exists: CLI-trained `--model-type xgboost --direction buy` models
    persist model_type="xgboost" (no "2class_buy" hint) but DO persist
    model_direction="buy". String-matching alone mis-maps them as 3-class.
    """

    def test_persisted_direction_wins_over_model_type_string(self) -> None:
        """A model_type without a direction hint still resolves via persisted field."""
        assert resolve_model_direction("xgboost", "buy") == "buy"
        assert resolve_model_direction("xgboost", "sell") == "sell"

    def test_falls_back_to_model_type_string_when_no_persisted_direction(self) -> None:
        """Old models (model_direction=None) keep string-match behavior (backward compat)."""
        assert resolve_model_direction("xgboost_2class_buy", None) == "buy"
        assert resolve_model_direction("xgboost_2class_sell", None) == "sell"

    def test_three_class_resolves_to_none(self) -> None:
        """Plain 3-class with no persisted direction stays 3-class (None)."""
        assert resolve_model_direction("xgboost_3class", None) is None
        assert resolve_model_direction("xgboost", None) is None

    def test_empty_or_missing_model_type_handled(self) -> None:
        """None/empty model_type must not crash; persisted direction still wins."""
        assert resolve_model_direction(None, "buy") == "buy"
        assert resolve_model_direction(None, None) is None
        assert resolve_model_direction("", None) is None


class TestSignalMappingConstants:
    """Test signal mapping constants are correct."""

    def test_prediction_to_signal_mapping(self) -> None:
        """
        3-class prediction to signal mapping.

        Model output (0, 1, 2) -> Trading signal (-1, 0, 1)
        """
        assert PREDICTION_TO_SIGNAL_3CLASS[0] == -1  # SELL -> SHORT
        assert PREDICTION_TO_SIGNAL_3CLASS[1] == 0  # HOLD -> HOLD
        assert PREDICTION_TO_SIGNAL_3CLASS[2] == 1  # BUY -> LONG

    def test_signal_to_prediction_mapping(self) -> None:
        """
        Signal to prediction (reverse mapping).

        Trading signal (-1, 0, 1) -> Model output (0, 1, 2)
        """
        assert SIGNAL_TO_PREDICTION_3CLASS[-1] == 0  # SHORT -> SELL
        assert SIGNAL_TO_PREDICTION_3CLASS[0] == 1  # HOLD -> HOLD
        assert SIGNAL_TO_PREDICTION_3CLASS[1] == 2  # LONG -> BUY

    def test_round_trip_conversion(self) -> None:
        """Mapping -> reverse mapping should be identity."""
        for pred in [0, 1, 2]:
            signal = PREDICTION_TO_SIGNAL_3CLASS[pred]
            restored = SIGNAL_TO_PREDICTION_3CLASS[signal]
            assert restored == pred


class TestConvertSignalsToPredictions:
    """
    Test convert_signals_to_predictions (signal space -> 3-class).

    BEHAVIOR: Hybrid backtest combines ML (outputs signals -1,0,1) with classic
    (outputs 0,1,2). combine_hybrid_predictions expects both in 3-class; without
    this conversion ML BUY (1) would never match classic BUY (2) -> zero trades.
    """

    def test_signals_to_predictions_basic(self) -> None:
        """-1→0 (SELL), 0→1 (HOLD), 1→2 (BUY)."""
        signals = np.array([-1, 0, 1, 1, 0, -1])
        result = convert_signals_to_predictions(signals)
        expected = np.array([0, 1, 2, 2, 1, 0])
        np.testing.assert_array_equal(result, expected)

    def test_signals_to_predictions_all_buy(self) -> None:
        """All LONG (1) -> all BUY (2)."""
        signals = np.array([1, 1, 1])
        result = convert_signals_to_predictions(signals)
        np.testing.assert_array_equal(result, np.array([2, 2, 2]))

    def test_signals_to_predictions_all_sell(self) -> None:
        """All SHORT (-1) -> all SELL (0)."""
        signals = np.array([-1, -1])
        result = convert_signals_to_predictions(signals)
        np.testing.assert_array_equal(result, np.array([0, 0]))

    def test_signals_to_predictions_empty(self) -> None:
        """Empty array returns empty array."""
        signals = np.array([], dtype=np.int32)
        result = convert_signals_to_predictions(signals)
        assert len(result) == 0

    def test_round_trip_with_convert_predictions_to_signals(self) -> None:
        """signals -> predictions -> signals should match original (3-class)."""
        predictions = np.array([0, 1, 2, 2, 1, 0])
        signals = convert_predictions_to_signals(predictions)
        back_to_pred = convert_signals_to_predictions(signals)
        np.testing.assert_array_equal(back_to_pred, predictions)


class TestConvertPredictionsToSignals:
    """
    Test convert_predictions_to_signals function.

    Found in:
    - infrastructure/ml/backtester.py:268
    - scripts/train_model_validation.py:65
    """

    def test_basic_conversion(self) -> None:
        """Basic prediction array conversion."""
        predictions = np.array([0, 1, 2, 2, 1, 0])
        signals = convert_predictions_to_signals(predictions)

        expected = np.array([-1, 0, 1, 1, 0, -1])
        np.testing.assert_array_equal(signals, expected)

    def test_all_buy_predictions(self) -> None:
        """All BUY predictions -> all LONG signals."""
        predictions = np.array([2, 2, 2, 2, 2])
        signals = convert_predictions_to_signals(predictions)

        expected = np.array([1, 1, 1, 1, 1])
        np.testing.assert_array_equal(signals, expected)

    def test_all_sell_predictions(self) -> None:
        """All SELL predictions -> all SHORT signals."""
        predictions = np.array([0, 0, 0, 0, 0])
        signals = convert_predictions_to_signals(predictions)

        expected = np.array([-1, -1, -1, -1, -1])
        np.testing.assert_array_equal(signals, expected)

    def test_all_hold_predictions(self) -> None:
        """All HOLD predictions -> all HOLD signals."""
        predictions = np.array([1, 1, 1, 1, 1])
        signals = convert_predictions_to_signals(predictions)

        expected = np.array([0, 0, 0, 0, 0])
        np.testing.assert_array_equal(signals, expected)

    def test_empty_array(self) -> None:
        """Empty array should return empty array."""
        predictions = np.array([])
        signals = convert_predictions_to_signals(predictions)

        assert len(signals) == 0

    def test_preserves_dtype_int(self) -> None:
        """Output should be integer type for signal values."""
        predictions = np.array([0, 1, 2])
        signals = convert_predictions_to_signals(predictions)

        assert signals.dtype in [np.int32, np.int64, int]


class TestConvertPredictionsToSignals2ClassBuy:
    """
    Test 2-class BUY model signal conversion.

    2-class BUY models predict: 0=NOT-BUY, 1=BUY
    Output signals: 0=HOLD, 1=LONG (no transformation needed)

    @see src.workers.tasks.training_tasks_job.infer_model_direction
    """

    def test_buy_model_basic_conversion(self) -> None:
        """2-class BUY: predictions unchanged (0→0, 1→1)."""
        predictions = np.array([0, 1, 0, 1, 1])
        signals = convert_predictions_to_signals(predictions, model_direction="buy")

        expected = np.array([0, 1, 0, 1, 1])
        np.testing.assert_array_equal(signals, expected)

    def test_buy_model_all_buy(self) -> None:
        """All BUY predictions stay as 1."""
        predictions = np.array([1, 1, 1, 1, 1])
        signals = convert_predictions_to_signals(predictions, model_direction="buy")

        expected = np.array([1, 1, 1, 1, 1])
        np.testing.assert_array_equal(signals, expected)

    def test_buy_model_all_not_buy(self) -> None:
        """All NOT-BUY predictions stay as 0."""
        predictions = np.array([0, 0, 0, 0, 0])
        signals = convert_predictions_to_signals(predictions, model_direction="buy")

        expected = np.array([0, 0, 0, 0, 0])
        np.testing.assert_array_equal(signals, expected)

    def test_buy_model_empty_array(self) -> None:
        """Empty array returns empty array."""
        predictions = np.array([], dtype=np.int32)
        signals = convert_predictions_to_signals(predictions, model_direction="buy")

        assert len(signals) == 0

    def test_buy_model_preserves_dtype(self) -> None:
        """Output should be int32."""
        predictions = np.array([0, 1])
        signals = convert_predictions_to_signals(predictions, model_direction="buy")

        assert signals.dtype == np.int32


class TestConvertPredictionsToSignals2ClassSell:
    """
    Test 2-class SELL model signal conversion.

    2-class SELL models predict: 0=NOT-SELL, 1=SELL
    Output signals: 0=HOLD, -1=SHORT

    @see src.workers.tasks.training_tasks_job.infer_model_direction
    """

    def test_sell_model_basic_conversion(self) -> None:
        """2-class SELL: 0→0 (HOLD), 1→-1 (SHORT)."""
        predictions = np.array([0, 1, 0, 1, 1])
        signals = convert_predictions_to_signals(predictions, model_direction="sell")

        expected = np.array([0, -1, 0, -1, -1])
        np.testing.assert_array_equal(signals, expected)

    def test_sell_model_all_sell(self) -> None:
        """All SELL predictions become -1."""
        predictions = np.array([1, 1, 1, 1, 1])
        signals = convert_predictions_to_signals(predictions, model_direction="sell")

        expected = np.array([-1, -1, -1, -1, -1])
        np.testing.assert_array_equal(signals, expected)

    def test_sell_model_all_not_sell(self) -> None:
        """All NOT-SELL predictions stay as 0."""
        predictions = np.array([0, 0, 0, 0, 0])
        signals = convert_predictions_to_signals(predictions, model_direction="sell")

        expected = np.array([0, 0, 0, 0, 0])
        np.testing.assert_array_equal(signals, expected)

    def test_sell_model_empty_array(self) -> None:
        """Empty array returns empty array."""
        predictions = np.array([], dtype=np.int32)
        signals = convert_predictions_to_signals(predictions, model_direction="sell")

        assert len(signals) == 0

    def test_sell_model_preserves_dtype(self) -> None:
        """Output should be int32."""
        predictions = np.array([0, 1])
        signals = convert_predictions_to_signals(predictions, model_direction="sell")

        assert signals.dtype == np.int32
