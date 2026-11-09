"""
Activation-time checks for ``TradingAutomation`` strategy snapshots.

Plan slice-06: block activation when snapshot market/exec surface is incompatible with
what the executor will run (compound v2 requires swap; promoted backtest market drift).
"""

from __future__ import annotations

from typing import Any

from src.domain.services.compound_v2_schedule import normalize_compound_leg_schedule_v2
from src.domain.services.trading_automation_execution_params import extract_automation_execution_params
from src.shared.constants.exchanges import MARKET_TYPE_SWAP
from src.shared.exceptions import ValidationError


def validate_snapshot_executable_for_activation(strategy_snapshot: dict[str, Any]) -> None:
    """
    Rules aligned with ``AutomationExecutorRunService`` tick gates (fail fast at activate).

    - Non-empty ``compound_leg_schedule_v2`` requires **swap** market in snapshot config.
    """
    snap = strategy_snapshot if isinstance(strategy_snapshot, dict) else {}
    v2 = normalize_compound_leg_schedule_v2(snap.get("compound_leg_schedule_v2"))
    if not v2:
        return
    params = extract_automation_execution_params(snap)
    if params.market_type != MARKET_TYPE_SWAP:
        raise ValidationError(
            message="Compound v2 schedule requires futures (swap) market type in the strategy snapshot.",
            details={
                "activation_violation": "compound_v2_requires_swap_market",
                "snapshot_market_type": params.market_type,
            },
        )


def validate_promoted_market_type_matches_backtest(
    *,
    strategy_snapshot: dict[str, Any],
    backtest_run_config: dict[str, Any] | None,
) -> None:
    """
    Block activation when promoted snapshot ``config.market_type`` drifts from the completed run.

    Spot backtest → futures automation (or reverse) without an explicit promotion path is high risk.
    """
    snap = strategy_snapshot if isinstance(strategy_snapshot, dict) else {}
    snap_params = extract_automation_execution_params(snap)
    run_params = extract_automation_execution_params(
        {"config": backtest_run_config if isinstance(backtest_run_config, dict) else {}},
    )
    if snap_params.market_type != run_params.market_type:
        raise ValidationError(
            message="Automation market_type does not match the promoted backtest run (edit snapshot in draft or create a new promotion).",
            details={
                "activation_violation": "market_type_drift_from_backtest",
                "snapshot_market_type": snap_params.market_type,
                "backtest_market_type": run_params.market_type,
            },
        )
