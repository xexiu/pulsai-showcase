"""
Trading Performance Optimization Objective (Sprint 2.0k) — backward-compat shim.

Re-exports the public surface so existing call sites continue to use::

    from src.infrastructure.ml.trading_objective import (
        TradingMetrics,
        TradingPerformanceObjective,
        RiskAdjustedTradingObjective,
        BottomDetectionObjective,
    )

Implementation now lives in three focused siblings:

- :mod:`trading_objective_base`     — :class:`TradingPerformanceObjective` +
  score-shaping thresholds (``HIGH_QUALITY_*``, ``POOR_*``).
- :mod:`trading_objective_metrics`  — :class:`TradingMetrics` (Sharpe / drawdown).
- :mod:`trading_objective_variants` — :class:`RiskAdjustedTradingObjective`
  and :class:`BottomDetectionObjective` subclasses.

WHY split:
- Traditional ML optimizes accuracy/F1 which reward predicting HOLD always (77%
  accuracy) but produce zero useful trading signals. Trading objectives reward
  profit, win rate, frequency, and risk-adjusted returns instead.
- Keeping the base class, metrics model, and risk-shaping variants in
  separate modules lets each piece evolve independently and stay testable.

Reference: trading_bots/backend/core/models/AbstractPredictor.objective_bottom_detection_trading

@see docs/02-technical/ML_PIPELINE.md
"""

from src.infrastructure.ml.trading_objective_base import (
    HIGH_QUALITY_RETURN_THRESHOLD,
    HIGH_QUALITY_WIN_RATE_THRESHOLD,
    POOR_RETURN_THRESHOLD,
    POOR_WIN_RATE_THRESHOLD,
    TradingPerformanceObjective,
)
from src.infrastructure.ml.trading_objective_metrics import TradingMetrics
from src.infrastructure.ml.trading_objective_variants import (
    BottomDetectionObjective,
    RiskAdjustedTradingObjective,
)

__all__ = (
    "HIGH_QUALITY_RETURN_THRESHOLD",
    "HIGH_QUALITY_WIN_RATE_THRESHOLD",
    "POOR_RETURN_THRESHOLD",
    "POOR_WIN_RATE_THRESHOLD",
    "BottomDetectionObjective",
    "RiskAdjustedTradingObjective",
    "TradingMetrics",
    "TradingPerformanceObjective",
)
