"""
Trading-performance metrics model + risk calculations.

Extracted from :mod:`trading_objective` so the objective module can stay
focused on score-shaping (weights, thresholds, bonuses/penalties). The model
owns its derived risk metrics (Sharpe ratio, max drawdown) as properties.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict

from src.shared.math.zero_dispersion import is_near_zero_std

# Minimum trade returns needed for Sharpe calculation
# WHY 2: Need at least 2 returns to calculate standard deviation
MIN_TRADE_RETURNS_FOR_SHARPE = 2


class TradingMetrics(BaseModel):
    """
    Trading performance metrics.

    WHY Pydantic:
    - Validates field types at construction
    - model_dump() replaces manual to_dict()
    - Properties (sharpe_ratio, etc.) preserved
    """

    model_config = ConfigDict(from_attributes=True)

    total_trades: int
    profitable_trades: int
    win_rate: float
    total_return: float
    avg_return_per_trade: float
    max_consecutive_losses: int
    # Sprint 2.0k: Trade history for risk-adjusted calculations
    trade_returns: list[float] | None = None  # Individual trade returns for Sharpe/drawdown

    def to_dict(self, include_returns: bool = False) -> dict[str, Any]:
        """
        Convert to dictionary.

        Args:
            include_returns: Whether to include trade_returns (can be large)
        """
        exclude = None if include_returns else {"trade_returns"}
        return self.model_dump(exclude_none=True, exclude=exclude)

    @property
    def sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio from trade returns.

        Sharpe = mean(returns) / std(returns)
        > 1.0 = good, > 2.0 = excellent

        Returns 0.0 if not enough data or zero variance.
        """
        if self.trade_returns is None or len(self.trade_returns) < MIN_TRADE_RETURNS_FOR_SHARPE:
            return 0.0

        returns_arr = np.array(self.trade_returns)
        mean = float(np.mean(returns_arr))
        std = float(np.std(returns_arr))

        if is_near_zero_std(std, mean):
            return 0.0

        return mean / std

    @property
    def max_drawdown(self) -> float:
        """
        Calculate maximum drawdown from trade returns.

        Max drawdown = largest peak-to-trough decline in cumulative returns.
        Range: 0.0 (no drawdown) to 1.0+ (100%+ loss from peak).

        WHY: Measures worst-case scenario risk.
        """
        if self.trade_returns is None or len(self.trade_returns) < 1:
            return 0.0

        # Calculate cumulative returns (equity curve)
        cumulative = np.cumprod(1 + np.array(self.trade_returns))

        # Running maximum
        running_max = np.maximum.accumulate(cumulative)

        # Drawdown at each point
        drawdown = (running_max - cumulative) / running_max

        return float(np.max(drawdown))
