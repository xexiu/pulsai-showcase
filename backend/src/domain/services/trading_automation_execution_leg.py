"""
Validate execution_leg_mode vs immutable strategy_type (snapshot semantics).

WHY:
- Hybrid snapshots may run full_hybrid, ml_only, or classic_only (subset = drift).
- ML-only snapshot cannot run classic_only; classic cannot run ml_only.
"""

from __future__ import annotations

from src.shared.constants.trading_automation import (
    STRATEGY_TYPE_CLASSIC,
    STRATEGY_TYPE_HYBRID,
    STRATEGY_TYPE_MODEL,
    ExecutionLegMode,
)
from src.shared.exceptions import ExecutionLegIncompatibleError


def default_execution_leg_mode_for_strategy(strategy_type: str) -> str:
    """Default leg mode when the client omits the field."""
    if strategy_type == STRATEGY_TYPE_HYBRID:
        return ExecutionLegMode.FULL_HYBRID.value
    if strategy_type == STRATEGY_TYPE_MODEL:
        return ExecutionLegMode.ML_ONLY.value
    if strategy_type == STRATEGY_TYPE_CLASSIC:
        return ExecutionLegMode.CLASSIC_ONLY.value
    return ExecutionLegMode.FULL_HYBRID.value


def validate_execution_leg_mode_for_strategy(strategy_type: str, execution_leg_mode: str) -> None:
    """
    Raise ExecutionLegIncompatibleError when the pair is impossible.

    ``strategy_type`` is the snapshot discriminator (same strings as BacktestRun).
    """
    allowed = allowed_execution_leg_modes(strategy_type)
    if execution_leg_mode not in allowed:
        raise ExecutionLegIncompatibleError(
            strategy_type=strategy_type,
            attempted_mode=execution_leg_mode,
        )


def allowed_execution_leg_modes(strategy_type: str) -> frozenset[str]:
    """Set of allowed persisted execution_leg_mode values for a strategy_type."""
    if strategy_type == STRATEGY_TYPE_HYBRID:
        return frozenset(
            {
                ExecutionLegMode.FULL_HYBRID.value,
                ExecutionLegMode.ML_ONLY.value,
                ExecutionLegMode.CLASSIC_ONLY.value,
            }
        )
    if strategy_type == STRATEGY_TYPE_MODEL:
        return frozenset({ExecutionLegMode.ML_ONLY.value})
    if strategy_type == STRATEGY_TYPE_CLASSIC:
        return frozenset({ExecutionLegMode.CLASSIC_ONLY.value})
    return frozenset()


def describe_execution_pipeline(strategy_type: str, execution_leg_mode: str) -> str:
    """
    Stable label for executor routing / logs (slice-04).

    Does not call ML; classifies how live execution should consume signals vs snapshot.
    """
    validate_execution_leg_mode_for_strategy(strategy_type, execution_leg_mode)
    if strategy_type == STRATEGY_TYPE_HYBRID:
        if execution_leg_mode == ExecutionLegMode.ML_ONLY.value:
            return "hybrid_snapshot_ml_only_skip_combiner"
        if execution_leg_mode == ExecutionLegMode.CLASSIC_ONLY.value:
            return "hybrid_snapshot_classic_only_ignore_ml_direction"
        return "hybrid_snapshot_full_combiner"
    if strategy_type == STRATEGY_TYPE_MODEL:
        return "ml_snapshot_ml_only"
    if strategy_type == STRATEGY_TYPE_CLASSIC:
        return "classic_snapshot_classic_only"
    return "unknown_strategy_type"
