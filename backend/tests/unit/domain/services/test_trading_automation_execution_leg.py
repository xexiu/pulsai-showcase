"""Behavior: execution_leg_mode allowed set vs strategy_type (plan slice-02 rules)."""

from __future__ import annotations

import pytest

from src.domain.services.trading_automation_execution_leg import (
    allowed_execution_leg_modes,
    default_execution_leg_mode_for_strategy,
    describe_execution_pipeline,
    validate_execution_leg_mode_for_strategy,
)
from src.shared.constants.trading_automation import (
    STRATEGY_TYPE_CLASSIC,
    STRATEGY_TYPE_HYBRID,
    STRATEGY_TYPE_MODEL,
    ExecutionLegMode,
)
from src.shared.exceptions import ExecutionLegIncompatibleError


def test_default_leg_mode_per_strategy_type() -> None:
    assert default_execution_leg_mode_for_strategy(STRATEGY_TYPE_HYBRID) == ExecutionLegMode.FULL_HYBRID.value
    assert default_execution_leg_mode_for_strategy(STRATEGY_TYPE_MODEL) == ExecutionLegMode.ML_ONLY.value
    assert default_execution_leg_mode_for_strategy(STRATEGY_TYPE_CLASSIC) == ExecutionLegMode.CLASSIC_ONLY.value


def test_hybrid_allows_all_three_modes() -> None:
    modes = allowed_execution_leg_modes(STRATEGY_TYPE_HYBRID)
    assert ExecutionLegMode.FULL_HYBRID.value in modes
    assert ExecutionLegMode.ML_ONLY.value in modes
    assert ExecutionLegMode.CLASSIC_ONLY.value in modes


def test_model_snapshot_rejects_classic_only() -> None:
    with pytest.raises(ExecutionLegIncompatibleError) as exc:
        validate_execution_leg_mode_for_strategy(STRATEGY_TYPE_MODEL, ExecutionLegMode.CLASSIC_ONLY.value)
    assert exc.value.details["strategy_type"] == STRATEGY_TYPE_MODEL
    assert exc.value.details["attempted_mode"] == ExecutionLegMode.CLASSIC_ONLY.value


def test_classic_snapshot_rejects_ml_only() -> None:
    with pytest.raises(ExecutionLegIncompatibleError):
        validate_execution_leg_mode_for_strategy(STRATEGY_TYPE_CLASSIC, ExecutionLegMode.ML_ONLY.value)


def test_comparison_strategy_has_no_allowed_modes() -> None:
    assert allowed_execution_leg_modes("comparison") == frozenset()


def test_describe_execution_pipeline_hybrid_ml_only() -> None:
    assert describe_execution_pipeline(STRATEGY_TYPE_HYBRID, ExecutionLegMode.ML_ONLY.value) == "hybrid_snapshot_ml_only_skip_combiner"


def test_describe_execution_pipeline_hybrid_classic_only() -> None:
    assert (
        describe_execution_pipeline(STRATEGY_TYPE_HYBRID, ExecutionLegMode.CLASSIC_ONLY.value) == "hybrid_snapshot_classic_only_ignore_ml_direction"
    )


def test_describe_execution_pipeline_hybrid_full() -> None:
    assert describe_execution_pipeline(STRATEGY_TYPE_HYBRID, ExecutionLegMode.FULL_HYBRID.value) == "hybrid_snapshot_full_combiner"


def test_describe_execution_pipeline_model() -> None:
    assert describe_execution_pipeline(STRATEGY_TYPE_MODEL, ExecutionLegMode.ML_ONLY.value) == "ml_snapshot_ml_only"


def test_describe_execution_pipeline_classic() -> None:
    assert describe_execution_pipeline(STRATEGY_TYPE_CLASSIC, ExecutionLegMode.CLASSIC_ONLY.value) == "classic_snapshot_classic_only"
