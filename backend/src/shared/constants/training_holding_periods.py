"""
Training / backtest holding-period SoT helpers.

Two concepts (do not conflate):

1. **Label horizon** — ``TRAINING_TIMEFRAME_POLICIES[tf].holding_periods`` in
   ``infrastructure.config.training`` drives target creation (forward window for
   BUY/SELL/HOLD labels). Varies by TF (e.g. 5m→12 bars, 1h→4 by default).

1b. **Regression label horizon** — ``get_regression_holding_periods(tf)`` converts
   ``REGRESSION_TARGET_FORWARD_HOURS`` (24h) into bars per timeframe for continuous
   targets (``volatility``, ``forward_range``, MFE/MAE). 5m ≠ 1h ≠ 4h.

2. **Backtest exit** — ``BacktestConfig.default_holding_periods`` (``DEFAULT_HOLDING_PERIODS``)
   is the default fixed-holding exit unless the API/CLI overrides ``holding_periods``.

Override at train time: ``train_model_cli --holding-periods N``.

Research grid below is for Phase 3+ sweeps when the default starves barrier exits on slower TFs.
"""

from __future__ import annotations

from src.shared.constants.cv_defaults import DEFAULT_HOLDING_PERIODS

# Empirical sweep tuple (bars). Cap 32 per product guard; try in order during research.
HOLDING_PERIOD_RESEARCH_GRID: tuple[int, ...] = (4, 6, 12, 24, 32)

HOLDING_PERIOD_RESEARCH_GRID_MAX: int = 32

__all__ = [
    "DEFAULT_HOLDING_PERIODS",
    "HOLDING_PERIOD_RESEARCH_GRID",
    "HOLDING_PERIOD_RESEARCH_GRID_MAX",
]
