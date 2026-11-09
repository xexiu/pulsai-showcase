"""
Signal conversion utilities.

CRITICAL: Signal conversion is fundamental to correct trading behavior.

3-class model predictions:
- 0 = SELL (model predicts price will go down)
- 1 = HOLD (model predicts sideways movement)
- 2 = BUY (model predicts price will go up)

Trading/API signals (backtester, response builders, regression threshold converter):
- -1 = SELL (SHORT)
- 0 = HOLD
- 1 = BUY (LONG)

Conversion formula: signal = prediction - 1 (3-class).
2-class and regression models normalize to the same API space (-1/0/1) at their boundary.

SoT: All signal value constants and int->action mapping live here. Used by:
- backtest_run_response (build_signals_response)
- infrastructure.ml.threshold_converter (regression → signals)
- Execution layer converts 3-class to API space via convert_predictions_to_signals

@see docs/04-structural/CODING_STANDARDS.md - Section 2.0 DON'T REINVENT THE WHEEL
"""

from typing import cast

import numpy as np
from numpy.typing import NDArray

from src.domain.enums import SignalAction
from src.shared.constants.predictions import (
    PREDICTION_CLASS_BUY,
    PREDICTION_CLASS_HOLD,
    PREDICTION_CLASS_SELL,
)

# ============================================================================
# SIGNAL MAPPING CONSTANTS
# ============================================================================
# SoT for class indices: shared.constants.predictions; mapping dicts stay here.

# 3-class model prediction to trading signal
# Model output (0=SELL, 1=HOLD, 2=BUY) -> Signal (-1=SHORT, 0=HOLD, 1=LONG)
PREDICTION_TO_SIGNAL_3CLASS: dict[int, int] = {
    PREDICTION_CLASS_SELL: -1,  # SELL prediction -> SHORT signal
    PREDICTION_CLASS_HOLD: 0,  # HOLD prediction -> HOLD signal
    PREDICTION_CLASS_BUY: 1,  # BUY prediction -> LONG signal
}

# Reverse mapping: trading signal to model prediction
# Signal (-1=SHORT, 0=HOLD, 1=LONG) -> Model output (0=SELL, 1=HOLD, 2=BUY)
SIGNAL_TO_PREDICTION_3CLASS: dict[int, int] = {
    -1: 0,  # SHORT signal -> SELL prediction
    0: 1,  # HOLD signal -> HOLD prediction
    1: 2,  # LONG signal -> BUY prediction
}

# API/response contract (SoT): classification and regression both produce this space.
# Used by build_signals_response, threshold_converter, execution _to_response_signals.
API_SIGNAL_SELL = -1
API_SIGNAL_HOLD = 0
API_SIGNAL_BUY = 1
API_SIGNAL_VALUES: tuple[int, ...] = (API_SIGNAL_SELL, API_SIGNAL_HOLD, API_SIGNAL_BUY)
#: The same three values as a set: what a signal column may contain (meta-labelling and the meta gate check it).
API_SIGNAL_VALUE_SET: frozenset[int] = frozenset(API_SIGNAL_VALUES)

#: An array of model class predictions or API signals -- any integer width (int8 signal columns, int64 predictions).
type SignalArray = NDArray[np.integer]

# SoT: int -> action name for API responses. No hardcoded dicts elsewhere.
API_SIGNAL_TO_ACTION: dict[int, str] = {
    API_SIGNAL_SELL: SignalAction.SELL.value,
    API_SIGNAL_HOLD: SignalAction.HOLD.value,
    API_SIGNAL_BUY: SignalAction.BUY.value,
}

# 3-class model index (0/1/2 or "0"/"1"/"2") -> action name for Telegram/notify/formatters.
# SoT: Used by notification_service, generate_signals, telegram handlers. No duplicate dicts.
CLASS_IDX_TO_ACTION_STR: dict[int | str, str] = {
    0: SignalAction.SELL.value,
    1: SignalAction.HOLD.value,
    2: SignalAction.BUY.value,
    "0": SignalAction.SELL.value,
    "1": SignalAction.HOLD.value,
    "2": SignalAction.BUY.value,
}


def is_regression_model_type(model_type: str | None) -> bool:
    """Return True when *model_type* indicates a regression (continuous-output) model.

    Case-insensitive substring match on 'regression'.  None / empty string → False.
    """
    return "regression" in (model_type or "").lower()


def signal_action_to_api_int(action: SignalAction) -> int:
    """Map a :class:`SignalAction` enum value to the API integer space (-1 / 0 / 1).

    Reuses the canonical API_SIGNAL_* constants so there is a single mapping SoT.
    Unknown actions (should not occur in practice) fall through to HOLD (0).
    """
    if action == SignalAction.BUY:
        return API_SIGNAL_BUY
    if action == SignalAction.SELL:
        return API_SIGNAL_SELL
    return API_SIGNAL_HOLD


def normalize_action_to_buy_sell_hold(action: str | int) -> str:
    """
    Normalize action to "BUY"/"SELL"/"HOLD" for Telegram, notify, formatters.

    Handles 3-class index (0/1/2 or "0"/"1"/"2") and already-normalized strings.
    SoT: Single implementation; use this instead of duplicating _ACTION_NORMALIZE
    in notification_service or _CLASS_IDX_TO_ACTION in generate_signals.

    Returns:
        One of SignalAction.BUY.value, SignalAction.SELL.value, SignalAction.HOLD.value.
    """
    if action in CLASS_IDX_TO_ACTION_STR:
        return CLASS_IDX_TO_ACTION_STR[action]
    if isinstance(action, str) and action in (
        SignalAction.BUY.value,
        SignalAction.SELL.value,
        SignalAction.HOLD.value,
    ):
        return action
    return CLASS_IDX_TO_ACTION_STR.get(str(action), SignalAction.HOLD.value)


# ============================================================================
# META-SCORE / MODEL VOTES BUILDERS (SoT: single place for ensemble scoring)
# ============================================================================


def compute_meta_score(action: str, confidence: float) -> float:
    """Compute meta-agent ensemble score from a single-model signal.

    Range: -1.0 (strong SELL) to +1.0 (strong BUY), 0.0 for HOLD.
    """
    if action == SignalAction.BUY.value:
        return confidence
    if action == SignalAction.SELL.value:
        return -confidence
    return 0.0


def build_single_model_vote(
    *,
    model_version: int | str,
    model_type: str,
    action: str,
    confidence: float,
    weight: float = 1.0,
    raw_action: str | None = None,
) -> dict[str, object]:
    """Build a single model vote dict for model_votes array.

    SoT: All model vote construction flows through here.

    ``raw_action`` is what the MODEL predicted, before any confidence override. It is always
    written, so the three states stay distinguishable:

        raw_action == action   the model chose this; nothing was suppressed
        raw_action != action   suppressed, and we know what it wanted
        raw_action is None     not recorded (an older row, or a caller that cannot know)

    Emitting the key only when it DIFFERS would make "unrecorded" read as "not suppressed",
    which is the flattering default that hides exactly the thing this field exists to expose.
    """
    return {
        "model_version": int(model_version) if isinstance(model_version, str) else model_version,
        "model_type": model_type,
        "action": action,
        "confidence": confidence,
        "weight": weight,
        "raw_action": raw_action,
    }


# ============================================================================
# DIRECTION RESOLUTION (SoT: how inference decides a model's class mapping)
# ============================================================================


def persisted_model_direction(metadata: object) -> str | None:
    """The direction string a model RECORDED, wherever on the artifact it recorded it.

    DISTINCT FROM :func:`resolve_model_direction`, which answers "which side does this model
    trade" and returns only "buy"/"sell"/None. This answers the PROVENANCE question -- what
    string is written down -- and deliberately passes through values that are not trading
    directions, such as "both", so the caller can interpret them. Collapsing the two would make
    `resolve_model_direction` return a value it must not return.

    WHY THE FALLBACK EXISTS, measured 2026-09-10. All 7 persisted `binary` models carry
    `model_direction: null` at the top level while the value sits in
    `training_config.model_direction`. Reading only the top-level field is why the capital cert
    for `BTC/USDT:1d:3:lightgbm` still logged "advertises a label space (0, 1) that cannot be
    placed" AFTER the mapping that was supposed to place it -- the mapping was right and the
    lookup never reached the data.

    Precedence is top-level FIRST: `training_config` is the request that was submitted, while
    the top-level field is what the pipeline stamped from what it actually knew, so a
    disagreement must resolve to the stamp.

    Args:
        metadata: a `ModelMetadata` (or any object exposing the same two attributes).

    Returns:
        The recorded direction string, or None when the artifact records none.
    """
    stamped = getattr(metadata, "model_direction", None)
    if isinstance(stamped, str) and stamped.strip():
        return stamped

    config = getattr(metadata, "training_config", None)
    if isinstance(config, dict):
        requested = cast("dict[str, object]", config).get("model_direction")  # a JSON object
        if isinstance(requested, str) and requested.strip():
            return requested
    return None


def resolve_model_direction(
    model_type: str | None,
    persisted_direction: str | None,
) -> str | None:
    """Resolve a model's directional class mapping for signal conversion.

    WHY this is the single source of truth:
    Inference (backtest hub, live, worker) historically derived direction by
    string-matching the ``model_type`` (``"2class_buy" in model_type``). That
    breaks for CLI-trained directional models: ``--model-type xgboost
    --direction buy`` persists ``model_type="xgboost"`` (no ``2class_*`` hint),
    so the match fails and a 2-class model is mis-mapped as 3-class (class 1 →
    HOLD → 0 actionable signals, the v98 bug).

    Resolution order:
    1. Persisted ``model_direction`` ("buy"/"sell") — authoritative, recorded at
       train time from what the pipeline actually knew.
    2. Fall back to the ``model_type`` string hint — keeps legacy models
       (``model_direction=None``, e.g. worker-trained ``xgboost_2class_buy``)
       behaving exactly as before.
    3. Otherwise ``None`` (3-class SELL/HOLD/BUY).

    Args:
        model_type: Persisted model_type string (may be None/empty).
        persisted_direction: ModelMetadata.model_direction (may be None).

    Returns:
        "buy", "sell", or None (3-class).
    """
    if persisted_direction in ("buy", "sell"):
        return persisted_direction

    model_type_str = (model_type or "").lower()
    if "2class_buy" in model_type_str:
        return "buy"
    if "2class_sell" in model_type_str:
        return "sell"
    return None


# ============================================================================
# CONVERSION FUNCTIONS
# ============================================================================


def convert_predictions_to_signals(
    predictions: SignalArray,
    model_direction: str | None = None,
) -> SignalArray:
    """
    Convert ML class predictions to trading signals.

    WHY this function exists:
    XGBoost outputs class indices (0, 1, 2), but backtester expects signals (-1, 0, 1).
    The mapping depends on the model type:

    - 3-class (model_direction=None): 0=SELL, 1=HOLD, 2=BUY → signals -1, 0, 1
    - 2-class BUY (model_direction="buy"): 0=NOT-BUY, 1=BUY → signals 0, 1
    - 2-class SELL (model_direction="sell"): 0=NOT-SELL, 1=SELL → signals 0, -1

    Args:
        predictions: Array of class predictions from model.predict()
        model_direction: "buy", "sell", or None (3-class)

    Returns:
        Array of trading signals: -1 (SHORT), 0 (HOLD), 1 (LONG)

    Examples:
        >>> convert_predictions_to_signals(np.array([0, 1, 2]))  # 3-class
        array([-1,  0,  1])
        >>> convert_predictions_to_signals(np.array([0, 1]), "buy")  # 2-class BUY
        array([0, 1])
        >>> convert_predictions_to_signals(np.array([0, 1]), "sell")  # 2-class SELL
        array([ 0, -1])

    Reference:
        trading_bots uses final_position: -1 (SHORT), 0 (NO ACTION), 1 (LONG)
    """
    if len(predictions) == 0:
        return predictions.astype(np.int32)

    if model_direction == "buy":
        # 2-class BUY: 0→HOLD, 1→BUY (API space)
        return np.where(predictions == 1, API_SIGNAL_BUY, API_SIGNAL_HOLD).astype(np.int32)

    if model_direction == "sell":
        # 2-class SELL: 0→HOLD, 1→SELL (API space)
        return np.where(predictions == 1, API_SIGNAL_SELL, API_SIGNAL_HOLD).astype(np.int32)

    # 3-class: 0→SELL, 1→HOLD, 2→BUY (API space)
    return (predictions - 1).astype(np.int32)


def signal_from_cuts(score: NDArray[np.float64], low: float | NDArray[np.float64], high: float | NDArray[np.float64]) -> NDArray[np.float64]:
    """A model score as an API signal by two cuts: BUY where score >= high, SELL where score <= low, HOLD between.

    One home for the three-way side a score's cuts give (the z12 ridge folds and rolling book, the z12 panel screen,
    ZOO-STACK); the cuts are the caller's -- one pair, or one per bar. A tie trades; a NaN score or cut holds. Where a
    score sits on both cuts (collapsed cuts) BUY wins, as the z12 ridge Pine port's `pred >= hi` comes first.
    """
    side = np.where(score <= low, float(API_SIGNAL_SELL), float(API_SIGNAL_HOLD))
    return np.where(score >= high, float(API_SIGNAL_BUY), side)


def convert_signals_to_predictions(signals: SignalArray) -> SignalArray:
    """
    Convert trading signals to 3-class prediction indices.

    Used when combining hybrid (ML + classic): ML path yields signals (-1, 0, 1)
    but combine_hybrid_predictions expects 3-class (0=SELL, 1=HOLD, 2=BUY).

    Args:
        signals: Array of trading signals (-1=SELL, 0=HOLD, 1=BUY)

    Returns:
        Array of 3-class predictions (0=SELL, 1=HOLD, 2=BUY)
    """
    if len(signals) == 0:
        return signals.astype(np.int32)
    # Vectorized: API space → 3-class; unknown values default to HOLD
    out = np.ones_like(signals, dtype=np.int32) * PREDICTION_CLASS_HOLD
    out[signals == API_SIGNAL_SELL] = PREDICTION_CLASS_SELL
    out[signals == API_SIGNAL_BUY] = PREDICTION_CLASS_BUY
    return out
