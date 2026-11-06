"""
Specialised trading-objective subclasses.

Risk-adjusted and bottom-detection variants extracted from
:mod:`trading_objective_base` so the base class can stay isolated from variant
score-shaping logic. Both this module and the base are re-exported via
:mod:`trading_objective` for backward compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.infrastructure.ml.trading_objective_base import TradingPerformanceObjective

if TYPE_CHECKING:
    from src.infrastructure.ml.trading_objective_metrics import TradingMetrics

logger = logging.getLogger(__name__)


class RiskAdjustedTradingObjective(TradingPerformanceObjective):
    """
    Risk-adjusted trading objective.

    Extends TradingPerformanceObjective with:
    - Sharpe ratio consideration
    - Maximum drawdown penalty
    - Calmar ratio

    Better for risk-averse strategies.
    """

    def __init__(
        self,
        drawdown_penalty_weight: float = 3.0,
        sharpe_weight: float = 6.0,
        **kwargs: Any,
    ) -> None:
        """
        Initialize RiskAdjustedTradingObjective.

        Args:
            drawdown_penalty_weight: Weight for max drawdown penalty
            sharpe_weight: Weight for Sharpe ratio in score
            **kwargs: Passed to parent TradingPerformanceObjective
        """
        super().__init__(**kwargs)
        self.drawdown_penalty_weight = drawdown_penalty_weight
        self.sharpe_weight = sharpe_weight

    def _calculate_score(self, metrics: TradingMetrics) -> float:
        """
        Calculate risk-adjusted score.

        Formula:
            risk_adjusted_score = base_score + sharpe_bonus - drawdown_penalty

        Where:
        - base_score: From parent TradingPerformanceObjective
        - sharpe_bonus: Sharpe ratio * sharpe_weight (rewards consistency)
        - drawdown_penalty: max_drawdown * drawdown_penalty_weight (penalizes risk)

        WHY risk adjustment?
        - High returns with high variance = risky
        - Consistent moderate returns = safer and often better long-term
        - Large drawdowns = psychologically difficult and can blow up accounts
        """
        base_score = super()._calculate_score(metrics)

        # Get risk metrics from trade history
        sharpe = metrics.sharpe_ratio
        max_dd = metrics.max_drawdown

        # Sharpe ratio bonus (rewards consistency)
        # Sharpe > 1.0 = good, > 2.0 = excellent
        sharpe_bonus = sharpe * self.sharpe_weight

        # Max drawdown penalty (penalizes risk)
        # 10% drawdown with weight 3.0 = -0.3 penalty
        # 50% drawdown with weight 3.0 = -1.5 penalty
        drawdown_penalty = max_dd * self.drawdown_penalty_weight

        # Combined risk-adjusted score
        risk_adjusted_score = base_score + sharpe_bonus - drawdown_penalty

        logger.debug(
            "RiskAdjustedScore: %.2f (base=%.2f, sharpe=%.2f bonus=%.2f, dd=%.2f penalty=%.2f)",
            risk_adjusted_score,
            base_score,
            sharpe,
            sharpe_bonus,
            max_dd,
            drawdown_penalty,
        )

        return risk_adjusted_score


class BottomDetectionObjective(TradingPerformanceObjective):
    """
    Optimized objective for bottom detection trading.

    WHY specialized objective for bottom detection?
    - Regular TradingPerformanceObjective treats all entries equally
    - Bottom detection requires STRONG recovery (high avg_return)
    - Quality matters more than quantity (high win_rate)
    - Bottoms that don't bounce strongly are not good bottoms

    Key differences from base:
    - Higher return_weight (25.0 vs 20.0) - bottoms need strong recovery
    - Higher win_rate_weight (8.0 vs 3.0) - quality over quantity
    - Quality bonus for win_rate > 60% AND avg_return > 0.8%
    - Heavy penalty for poor bottom detection

    Reference: trading_bots/backend/core/models/AbstractPredictor.objective_bottom_detection_trading
    """

    def __init__(
        self,
        return_weight: float = 25.0,  # Higher than default 20 (bottoms need strong recovery)
        win_rate_weight: float = 8.0,  # Higher than default 3 (quality matters)
        quality_bonus: float = 5.0,  # Bonus for high-quality trades
        poor_penalty: float = 10.0,  # Penalty for poor bottom detection
        quality_win_rate_threshold: float = 0.6,  # Win rate threshold for bonus
        quality_return_threshold: float = 0.008,  # Return threshold for bonus (0.8%)
        poor_win_rate_threshold: float = 0.4,  # Win rate threshold for penalty
        poor_return_threshold: float = 0.002,  # Return threshold for penalty (0.2%)
        **kwargs: Any,
    ) -> None:
        """
        Initialize BottomDetectionObjective.

        Args:
            return_weight: Weight for avg return per trade (default 25.0, higher than base)
            win_rate_weight: Weight for win rate (default 8.0, higher than base)
            quality_bonus: Bonus for high-quality trades (default 5.0)
            poor_penalty: Penalty for poor detection (default 10.0)
            quality_win_rate_threshold: Min win rate for bonus (default 0.6 = 60%)
            quality_return_threshold: Min avg return for bonus (default 0.008 = 0.8%)
            poor_win_rate_threshold: Max win rate before penalty (default 0.4 = 40%)
            poor_return_threshold: Max return before penalty (default 0.002 = 0.2%)
            **kwargs: Passed to parent TradingPerformanceObjective
        """
        super().__init__(
            return_weight=return_weight,
            win_rate_weight=win_rate_weight,
            **kwargs,
        )
        self.quality_bonus = quality_bonus
        self.poor_penalty = poor_penalty
        self.quality_win_rate_threshold = quality_win_rate_threshold
        self.quality_return_threshold = quality_return_threshold
        self.poor_win_rate_threshold = poor_win_rate_threshold
        self.poor_return_threshold = poor_return_threshold

    def _calculate_score(self, metrics: TradingMetrics) -> float:
        """
        Calculate bottom detection optimized score.

        Formula:
            score = base_score + quality_bonus - poor_penalty

        Where:
        - base_score: From parent (already has higher return_weight)
        - quality_bonus: +5.0 if win_rate > 60% AND avg_return > 0.8%
        - poor_penalty: -10.0 if win_rate < 40% OR avg_return < 0.2%

        WHY these thresholds?
        - Bottom detection should be high conviction (60%+ win rate)
        - Bottoms should bounce significantly (0.8%+ avg return)
        - Poor detection (< 40% win rate) is worse than random
        - Low returns (< 0.2%) means picking false bottoms
        """
        base_score = super()._calculate_score(metrics)

        # Quality bonus for high-quality bottom entries
        # WHY: Reward models that find REAL bottoms with strong recovery
        is_quality = metrics.win_rate > self.quality_win_rate_threshold and metrics.avg_return_per_trade > self.quality_return_threshold
        if is_quality:
            base_score += self.quality_bonus

        # Penalty for poor bottom detection
        # WHY: Punish models that trigger on false bottoms
        is_poor = metrics.win_rate < self.poor_win_rate_threshold or metrics.avg_return_per_trade < self.poor_return_threshold
        if is_poor:
            base_score -= self.poor_penalty

        logger.debug(
            "BottomDetectionScore: %.2f (win_rate=%.2f, avg_return=%.4f, quality=%s, poor=%s)",
            base_score,
            metrics.win_rate,
            metrics.avg_return_per_trade,
            is_quality,
            is_poor,
        )

        return base_score
