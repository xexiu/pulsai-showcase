"""
Extract automation execution parameters from persisted ``strategy_snapshot``.

SoT: promoted snapshot uses ``run.config`` shape from backtest. The auto pipeline
reads market_type / leverage / min_compound_step_pct from the snapshot to size
the CCXT call. Previously named ``trading_automation_paper_params`` — renamed
in Epic B since the auto pipeline is no longer paper-specific.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.shared.constants.exchanges import MARKET_TYPE_SPOT, MARKET_TYPE_SWAP, MarketType


@dataclass(frozen=True)
class AutomationExecutionParams:
    """Overrides applied to the automation CCXT call (market_type / leverage / DCA step)."""

    min_compound_step_pct: Decimal | None
    market_type: MarketType
    leverage: int | None


def extract_automation_execution_params(strategy_snapshot: dict[str, Any]) -> AutomationExecutionParams:
    """Defaults: spot, no leverage, min_step from config when present."""
    cfg = strategy_snapshot.get("config")
    if not isinstance(cfg, dict):
        cfg = {}

    min_step: Decimal | None = None
    raw_step = cfg.get("min_compound_step_pct")
    if raw_step is not None:
        min_step = Decimal(str(raw_step))

    mt_raw = cfg.get("market_type")
    market_type: MarketType = MARKET_TYPE_SWAP if mt_raw in (MARKET_TYPE_SWAP, "swap", "futures") else MARKET_TYPE_SPOT

    lev: int | None = None
    raw_lev = cfg.get("leverage")
    if raw_lev is not None:
        try:
            lev = int(raw_lev)
        except TypeError, ValueError:
            lev = None

    if market_type == MARKET_TYPE_SPOT:
        lev = None

    return AutomationExecutionParams(
        min_compound_step_pct=min_step,
        market_type=market_type,
        leverage=lev,
    )
