"""
3-class prediction class indices (SoT for backtest, ML, and signal conversion).

Model output contract: 0=SELL, 1=HOLD, 2=BUY. Used by:
- backtest_execution (combine_hybrid_predictions, combine_ml_predictions)
- backtest_tasks/predictions_ml and predictions_classic
- shared.utils.signals (PREDICTION_TO_SIGNAL_3CLASS, convert_*)
- trainer_metrics (signal_map 0->-1, 1->0, 2->1)

Define once here; import everywhere. Unblocks backtest refactor (§13 #4).
@see docs/04-structural/BACKEND_ARCHITECT_AUDIT.md §6.4, §13 #6
"""

# 3-class model prediction class indices (SELL=0, HOLD=1, BUY=2)
PREDICTION_CLASS_SELL = 0
PREDICTION_CLASS_HOLD = 1
PREDICTION_CLASS_BUY = 2

__all__ = [
    "PREDICTION_CLASS_BUY",
    "PREDICTION_CLASS_HOLD",
    "PREDICTION_CLASS_SELL",
]
