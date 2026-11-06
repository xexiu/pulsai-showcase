"""
Base trading-performance objective.

Houses :class:`TradingPerformanceObjective` and its score-shaping thresholds
so that :mod:`trading_objective_variants` can import the base class without a
circular dependency on :mod:`trading_objective` (which now exists purely as a
backward-compatibility shim re-exporting base + metrics + variants).

@see :mod:`trading_objective_metrics` for the :class:`TradingMetrics` model.
@see :mod:`trading_objective_variants` for risk-adjusted / bottom-detection.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from src.infrastructure.ml.trading_objective_metrics import TradingMetrics

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Quality bonus thresholds (public — variants reuse the names for parity).
# WHY 0.6: Win rate > 60% indicates consistent profitable trading.
HIGH_QUALITY_WIN_RATE_THRESHOLD = 0.6
# WHY 0.005: Average return > 0.5% per trade indicates profitable strategy.
HIGH_QUALITY_RETURN_THRESHOLD = 0.005

# Poor-performance thresholds.
# WHY 0.4: Win rate < 40% is worse than random (50% for binary).
POOR_WIN_RATE_THRESHOLD = 0.4
# WHY 0.001: Average return < 0.1% means barely profitable or losing.
POOR_RETURN_THRESHOLD = 0.001

# Score-shaping constants (private — internal scoring weights).
_NO_DATA_PENALTY = -1000.0
_PER_MISSING_TRADE_PENALTY = -100.0
_QUALITY_TRADE_BONUS = 5.0
_POOR_PERFORMANCE_PENALTY = 10.0
_MAX_CONSECUTIVE_LOSS_PENALTY = 0.5
_CONSECUTIVE_LOSS_PENALTY_PER_LOSS = 0.1
_TRADE_FREQUENCY_NORMALIZER = 50  # Trades needed to saturate frequency component


class TradingPerformanceObjective:
    """
    Optuna objective for trading performance optimization.

    Instead of optimizing for classification metrics,
    this objective optimizes for actual PROFIT.

    How it works:
    1. Get model predictions (probabilities)
    2. Apply threshold to generate buy signals
    3. Calculate hypothetical trades using future prices
    4. Score based on profit, win rate, and frequency

    Example with Optuna:
        def objective(trial):
            # Train model
            model = XGBClassifier(**params)
            model.fit(X_train, y_train)

            # Get probabilities
            y_proba = model.predict_proba(X_test)[:, 1]

            # Calculate trading score
            objective = TradingPerformanceObjective()
            threshold = trial.suggest_float("threshold", 0.3, 0.9)
            score = objective.calculate_score(
                y_true=y_test,
                y_proba=y_proba,
                df=df_test,
                threshold=threshold,
            )
            return score
    """

    def __init__(
        self,
        lookforward_periods: list[int] | None = None,
        transaction_cost: float = 0.001,  # 0.1% per trade (round trip)
        min_trades: int = 3,  # Minimum trades to calculate metrics
        return_weight: float = 20.0,  # Weight for avg return per trade
        win_rate_weight: float = 3.0,  # Weight for win rate
        frequency_weight: float = 0.3,  # Weight for trade frequency
    ) -> None:
        """
        Initialize TradingPerformanceObjective.

        Args:
            lookforward_periods: Periods to calculate future returns [3, 6, 12]
            transaction_cost: Cost per trade as fraction (0.001 = 0.1%)
            min_trades: Minimum trades required for valid score
            return_weight: Weight for average return per trade (higher = more important)
            win_rate_weight: Weight for win rate
            frequency_weight: Weight for trade frequency
        """
        self.lookforward_periods = lookforward_periods or [3, 6, 12]
        self.transaction_cost = transaction_cost
        self.min_trades = min_trades
        self.return_weight = return_weight
        self.win_rate_weight = win_rate_weight
        self.frequency_weight = frequency_weight

    def calculate_score(
        self,
        y_true: NDArray[np.int_],
        y_proba: NDArray[np.float64],
        df: pl.DataFrame,
        threshold: float = 0.5,
        return_metrics: bool = False,
    ) -> float | tuple[float, dict[str, Any]]:
        """
        Calculate trading performance score.

        This is the main scoring function for Optuna optimization.

        Args:
            y_true: Actual targets (for reference, not directly used in scoring)
            y_proba: Model prediction probabilities
            df: DataFrame with OHLCV data (must have 'close' column)
            threshold: Confidence threshold for generating signals
            return_metrics: If True, return (score, metrics_dict)

        Returns:
            score: Numeric score for Optuna (higher is better)
            metrics: Optional dict with detailed metrics

        Raises:
            ValueError: If lengths don't match
        """
        # `y_true` is part of every objective variant's signature so callers can swap them
        # freely; this one scores on PRICE, not on label agreement. Binding it says that in
        # code — a suppression would only have said it to the linter.
        _ = y_true

        # Validate inputs
        if len(y_proba) != len(df):
            msg = f"y_proba length ({len(y_proba)}) must match df length ({len(df)})"
            raise ValueError(msg)

        # Handle empty data
        if len(y_proba) == 0:
            if return_metrics:
                return _NO_DATA_PENALTY, {"error": "empty_data"}
            return _NO_DATA_PENALTY

        # Generate buy signals based on threshold
        buy_signals = y_proba >= threshold

        # No signals → penalize heavily
        if buy_signals.sum() == 0:
            if return_metrics:
                return _NO_DATA_PENALTY, {"error": "no_signals", "threshold": threshold}
            return _NO_DATA_PENALTY

        # Calculate trading performance
        metrics = self._calculate_trading_metrics(buy_signals, df)

        # Not enough trades → penalize
        if metrics.total_trades < self.min_trades:
            score = _PER_MISSING_TRADE_PENALTY * (self.min_trades - metrics.total_trades)
            if return_metrics:
                return score, metrics.to_dict()
            return score

        # Calculate final score
        score = self._calculate_score(metrics)

        if return_metrics:
            return score, metrics.to_dict()
        return score

    def _calculate_trading_metrics(
        self,
        buy_signals: NDArray[np.bool_],
        df: pl.DataFrame,
    ) -> TradingMetrics:
        """
        Calculate trading metrics from signals.

        For each buy signal, calculate the return over lookforward periods
        and take the MAX (best exit within window).

        Args:
            buy_signals: Boolean array of buy signals
            df: DataFrame with 'close' prices

        Returns:
            TradingMetrics with all calculated values (including trade_returns for risk calc)
        """
        close_prices = df["close"].to_numpy()
        n = len(close_prices)

        total_trades = 0
        profitable_trades = 0
        total_return = 0.0
        max_consecutive_losses = 0
        current_consecutive_losses = 0
        # Sprint 2.0k: Track individual trade returns for Sharpe/drawdown
        trade_returns_list: list[float] = []

        for i in range(n):
            if not buy_signals[i]:
                continue

            total_trades += 1
            entry_price = close_prices[i]

            # Calculate returns for each lookforward period
            period_returns: list[float] = []
            for period in self.lookforward_periods:
                exit_idx = i + period
                if exit_idx < n:
                    exit_price = close_prices[exit_idx]
                    trade_return = (exit_price / entry_price) - 1
                    period_returns.append(trade_return)

            if not period_returns:
                continue

            # Take best exit (max return)
            trade_return = max(period_returns)

            # Apply transaction cost
            trade_return -= self.transaction_cost

            total_return += trade_return
            trade_returns_list.append(trade_return)  # Store for risk metrics

            # Track wins/losses
            if trade_return > 0:
                profitable_trades += 1
                current_consecutive_losses = 0
            else:
                current_consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)

        # Calculate derived metrics
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0.0
        avg_return = total_return / total_trades if total_trades > 0 else 0.0

        return TradingMetrics(
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            win_rate=win_rate,
            total_return=total_return,
            avg_return_per_trade=avg_return,
            max_consecutive_losses=max_consecutive_losses,
            trade_returns=trade_returns_list,  # Now populated!
        )

    def _calculate_score(self, metrics: TradingMetrics) -> float:
        """
        Calculate final score from metrics.

        Formula (from reference project):
            score = (
                avg_return_per_trade * return_weight +
                win_rate * win_rate_weight +
                trade_frequency_score * frequency_weight
            )

        Args:
            metrics: Calculated trading metrics

        Returns:
            Final score (higher is better)
        """
        # Avoid division by zero
        if metrics.total_trades == 0:
            return _NO_DATA_PENALTY

        # Trade frequency score (capped to prevent gaming)
        # Normalize by expected number of trades
        frequency_score = min(1.0, metrics.total_trades / _TRADE_FREQUENCY_NORMALIZER)

        # Consecutive loss penalty
        consecutive_loss_penalty = min(
            _MAX_CONSECUTIVE_LOSS_PENALTY,
            metrics.max_consecutive_losses * _CONSECUTIVE_LOSS_PENALTY_PER_LOSS,
        )

        # Main score components
        score = (
            metrics.avg_return_per_trade * self.return_weight
            + metrics.win_rate * self.win_rate_weight
            + frequency_score * self.frequency_weight
            - consecutive_loss_penalty
        )

        # Bonus for high-quality trades
        if metrics.win_rate > HIGH_QUALITY_WIN_RATE_THRESHOLD and metrics.avg_return_per_trade > HIGH_QUALITY_RETURN_THRESHOLD:
            score += _QUALITY_TRADE_BONUS

        # Penalty for poor performance
        if metrics.win_rate < POOR_WIN_RATE_THRESHOLD or metrics.avg_return_per_trade < POOR_RETURN_THRESHOLD:
            score -= _POOR_PERFORMANCE_PENALTY

        logger.debug(
            "TradingScore: %.2f (trades=%d, win_rate=%.2f, avg_return=%.4f)",
            score,
            metrics.total_trades,
            metrics.win_rate,
            metrics.avg_return_per_trade,
        )

        return score
