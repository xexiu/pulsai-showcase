"""
Training Configuration

Default training parameters and performance targets for ML models.
Constants defined here are the Single Source of Truth for training defaults.
API schemas, pipeline constructors, and config endpoints all import from here.

@see docs/02-technical/ML_PIPELINE.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.shared.constants.cv_defaults import DEFAULT_HOLDING_PERIODS
from src.shared.constants.training_defaults import (
    DEFAULT_EXIT_STRATEGY,
    DEFAULT_OPTIMIZATION_MODE,
    DEFAULT_OPTIMIZATION_OBJECTIVE,
    DEFAULT_OPTUNA_TRIALS,
    DEFAULT_TRAINING_DAYS,
)

# =============================================================================
# Training Defaults (Single Source of Truth)
# WHY here (not in training_schemas.py): Infrastructure config is the foundation
# layer. API schemas (in routes/) can import from here, but importing the other
# direction (infra → API) causes circular imports because route modules trigger
# auth dependency loading.
# Scalar defaults live in src.shared.constants.training_defaults; this module adds
# Pydantic models and policies that compose them.
# =============================================================================


@dataclass(frozen=True)
class TrainingTimeframePolicy:
    """Training label thresholds and horizon for a supported timeframe."""

    threshold_pct: float
    holding_periods: int


TRAINING_TIMEFRAME_POLICIES: dict[str, TrainingTimeframePolicy] = {
    # 1m (LTF since 2026-10-11) DERIVED from 5m, not invented: it labels the same one-hour forward
    # move. Horizon = 5m's 12 bars scaled by bars-per-day (x5) = 60 bars; the same wall-clock window
    # sees the same forward-return distribution, so 5m's 0.3% threshold carries over unchanged.
    # (60 bars sits inside the owner's 240-bar / 4 h 1m max hold.)
    "1m": TrainingTimeframePolicy(threshold_pct=0.3, holding_periods=60),
    "5m": TrainingTimeframePolicy(threshold_pct=0.3, holding_periods=12),
    "15m": TrainingTimeframePolicy(threshold_pct=0.5, holding_periods=8),
    "30m": TrainingTimeframePolicy(threshold_pct=0.75, holding_periods=6),
    "1h": TrainingTimeframePolicy(threshold_pct=1.0, holding_periods=DEFAULT_HOLDING_PERIODS),
    # 2h/6h interpolated into the existing ladder on LOG duration, which is the shape the ladder
    # already has (1h→4h doubles the threshold's distance per doubling, not per hour): 2h sits
    # halfway between 1h (1.0) and 4h (1.5); 6h sits ~0.59 of the way from 4h (1.5) to 8h (1.75).
    # Holding periods follow their neighbours, which all take the default.
    "2h": TrainingTimeframePolicy(threshold_pct=1.25, holding_periods=DEFAULT_HOLDING_PERIODS),
    "4h": TrainingTimeframePolicy(threshold_pct=1.5, holding_periods=DEFAULT_HOLDING_PERIODS),
    "6h": TrainingTimeframePolicy(threshold_pct=1.65, holding_periods=DEFAULT_HOLDING_PERIODS),
    "8h": TrainingTimeframePolicy(threshold_pct=1.75, holding_periods=DEFAULT_HOLDING_PERIODS),
    "12h": TrainingTimeframePolicy(threshold_pct=1.85, holding_periods=4),
    "1d": TrainingTimeframePolicy(threshold_pct=2.0, holding_periods=3),
    "3d": TrainingTimeframePolicy(threshold_pct=3.0, holding_periods=2),
    "1w": TrainingTimeframePolicy(threshold_pct=4.0, holding_periods=2),
}

# Forward window for continuous regression targets (volatility, forward_range, MFE/MAE).
# Calendar SoT: ~24h ahead — matches nonprice 4h vol (6 bars) and 1d range (1 bar). On 1m that is
# 1,440 bars: a calendar-day forecast window by design, not a book's hold, so no 1m special case.
REGRESSION_TARGET_FORWARD_HOURS: float = 24.0


def get_regression_holding_periods(timeframe: str) -> int:
    """Bars for regression label horizon — scales with timeframe (5m ≠ 1h ≠ 4h).

    Uses ``REGRESSION_TARGET_FORWARD_HOURS`` wall-clock window divided by candle duration.
    Classification labels still use ``TrainingTimeframePolicy.holding_periods``.
    """
    get_training_timeframe_policy(timeframe)
    from src.shared.constants.timeframes import TIMEFRAME_MS

    tf_ms = TIMEFRAME_MS.get(timeframe)
    if tf_ms is None:
        supported = sorted(TRAINING_TIMEFRAME_POLICIES)
        msg = f"Unsupported regression timeframe '{timeframe}'. Supported: {supported}"
        raise ValueError(msg)
    forward_ms = REGRESSION_TARGET_FORWARD_HOURS * 3600 * 1000
    return max(1, round(forward_ms / tf_ms))


def get_training_timeframe_policy(timeframe: str) -> TrainingTimeframePolicy:
    """
    Return the explicit training policy for a supported timeframe.

    WHY fail fast:
    - Silent fallback lets config/public support one timeframe while training uses
      another timeframe's generic label thresholds
    - Training target behavior must be deliberate for every supported timeframe
    """
    policy = TRAINING_TIMEFRAME_POLICIES.get(timeframe)
    if policy is None:
        supported = sorted(TRAINING_TIMEFRAME_POLICIES)
        msg = f"Unsupported training timeframe '{timeframe}'. Add an explicit policy. Supported: {supported}"
        raise ValueError(msg)
    return policy


class TrainingDefaults(BaseModel):
    """
    Default training parameters.

    WHY Pydantic:
    - Validates config at construction
    - Consistent with other config classes

    WHY Field constraints:
    - n_trials=0 → Optuna does nothing (silent failure)
    - cv_folds=1 → TimeSeriesSplit needs at least 2 splits
    - Zero-day windows → walk-forward validation breaks

    SPRINT 1.6 ADDITIONS:
    - optimization_objectives: Multi-objective support (accuracy + Sharpe)
    - sharpe_target: Minimum acceptable Sharpe ratio
    - max_drawdown_target: Maximum allowed drawdown
    - training_window_days: Configurable training window
    """

    model_config = ConfigDict(from_attributes=True)

    n_trials: int = Field(default=DEFAULT_OPTUNA_TRIALS, gt=0)
    optimization_mode: str = DEFAULT_OPTIMIZATION_MODE  # fast, standard, thorough
    cv_folds: int = Field(default=5, ge=2)
    scoring: str = DEFAULT_OPTIMIZATION_OBJECTIVE
    min_training_samples: int = Field(default=1000, gt=0)

    # Walk-forward validation settings
    # WHY gt=0: Zero-length windows cause division by zero or infinite loops
    walk_forward_train_days: int = Field(default=60, gt=0)
    walk_forward_test_days: int = Field(default=14, gt=0)
    walk_forward_step_days: int = Field(default=7, gt=0)
    # WalkForwardValidator: anchored = expanding train (historical default); rolling = fixed train + slide
    walk_forward_window_mode: Literal["anchored", "rolling"] = "anchored"
    walk_forward_embargo_days: int = Field(
        default=0,
        ge=0,
        description="Gap in days after train before test; only used when walk_forward_window_mode is rolling.",
    )

    # Multi-objective optimization (Sprint 1.6)
    # Options: accuracy, sharpe_ratio, profit_factor, f1_score
    optimization_objectives: list[str] = [DEFAULT_OPTIMIZATION_OBJECTIVE]

    # Trading-specific targets for multi-objective
    # NOTE: sharpe_target NOT constrained — can be negative for experimentation
    sharpe_target: float = 1.5
    max_drawdown_target: float = 0.20  # Maximum 20% drawdown

    # Configurable training window options (Sprint 1.6)
    # Available options: 60, 90, 180, 365 days
    training_window_days: int = Field(default=60, gt=0)

    @model_validator(mode="after")
    def walk_forward_embargo_allowed_only_for_rolling(self) -> TrainingDefaults:
        """
        Embargo gaps train from test only in rolling geometry; anchored folds do not use it.
        """
        if self.walk_forward_window_mode == "anchored" and self.walk_forward_embargo_days != 0:
            raise ValueError("walk_forward_embargo_days must be 0 when walk_forward_window_mode is 'anchored'")
        return self


class PerformanceTargets(BaseModel):
    """
    Performance targets for monitoring.

    WHY Pydantic: Consistent with other config classes.

    NOTE: No Field constraints on these fields intentionally.
    These are monitoring thresholds, not safety-critical values.
    Wrong values cause misleading alerts, not crashes or data corruption.
    """

    model_config = ConfigDict(from_attributes=True)

    # Latency thresholds (milliseconds)
    max_inference_ms: int = 50
    max_feature_calc_ms: int = 20
    max_cache_lookup_ms: int = 2

    # Model quality thresholds
    min_model_accuracy: float = 0.55
    min_sharpe_ratio: float = 1.0
    min_accuracy_7d: float = 0.55  # Rolling 7-day minimum
    max_accuracy_drop: float = 0.10  # Max allowed drop from baseline

    # Latency anomaly detection thresholds
    latency_p99_warning_ms: int = 50
    latency_p99_critical_ms: int = 100
    latency_p99_rollback_ms: int = 100


__all__ = [
    "DEFAULT_EXIT_STRATEGY",
    "DEFAULT_HOLDING_PERIODS",
    "DEFAULT_OPTIMIZATION_MODE",
    "DEFAULT_OPTIMIZATION_OBJECTIVE",
    "DEFAULT_OPTUNA_TRIALS",
    "DEFAULT_TRAINING_DAYS",
    "REGRESSION_TARGET_FORWARD_HOURS",
    "TRAINING_TIMEFRAME_POLICIES",
    "PerformanceTargets",
    "TrainingDefaults",
    "TrainingTimeframePolicy",
    "get_regression_holding_periods",
    "get_training_timeframe_policy",
]
