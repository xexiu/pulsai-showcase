"""
Trading automation (manual vs auto plan) — server-side enums and string SoT.

Legacy module-level strings remain for imports that predate StrEnum.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

# --- Lifecycle (persisted on trading_automations.status) ---
AUTOMATION_STATUS_DRAFT = "draft"
AUTOMATION_STATUS_ACTIVE = "active"
AUTOMATION_STATUS_PAUSED = "paused"
AUTOMATION_STATUS_KILLED = "killed"

AUTOMATION_STATUSES: frozenset[str] = frozenset(
    {
        AUTOMATION_STATUS_DRAFT,
        AUTOMATION_STATUS_ACTIVE,
        AUTOMATION_STATUS_PAUSED,
        AUTOMATION_STATUS_KILLED,
    },
)


class TradingAutomationStatus(StrEnum):
    """Lifecycle of a TradingAutomation aggregate."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    KILLED = "killed"


# PATCH ``strategy_snapshot`` only while ``status == draft`` (slice-02: no silent policy drift).
STRATEGY_SNAPSHOT_LOCKED_UNLESS_DRAFT_MESSAGE: Final[str] = "Strategy snapshot cannot be modified unless the automation is in draft."


# --- Execution leg vs snapshot (plan: hybrid / ml / classic) ---
EXECUTION_LEG_FULL_HYBRID = "full_hybrid"
EXECUTION_LEG_ML_ONLY = "ml_only"
EXECUTION_LEG_CLASSIC_ONLY = "classic_only"

EXECUTION_LEG_MODES: frozenset[str] = frozenset(
    {
        EXECUTION_LEG_FULL_HYBRID,
        EXECUTION_LEG_ML_ONLY,
        EXECUTION_LEG_CLASSIC_ONLY,
    },
)


class ExecutionLegMode(StrEnum):
    """How signal legs run vs the promoted snapshot."""

    FULL_HYBRID = "full_hybrid"
    ML_ONLY = "ml_only"
    CLASSIC_ONLY = "classic_only"


class AutomationExecutionMode(StrEnum):
    """Auto-execution mode for a TradingAutomation. Only ``FULL_AUTO`` is live."""

    FULL_AUTO = "full_auto"


# Swap preflight floor when snapshot omits leverage (executor enqueue).
AUTOMATION_DEFAULT_SWAP_LEVERAGE: Final[int] = 1


class AutomationSource(StrEnum):
    """Lineage / origin of the automation row."""

    PROMOTED_FROM_BACKTEST = "promoted_from_backtest"
    PRODUCTION_CATALOG = "production_catalog"
    USER_OVERRIDE = "user_override"


# Aligns with BacktestRun.strategy_type (StrategyType).
STRATEGY_TYPE_MODEL = "model"
STRATEGY_TYPE_CLASSIC = "classic"
STRATEGY_TYPE_HYBRID = "hybrid"
