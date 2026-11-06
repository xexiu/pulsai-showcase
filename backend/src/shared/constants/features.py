"""
Feature and training constants (SoT for feature selection and validation).

Single source of truth for DEFAULT_MAX_FEATURES, DEFAULT_MIN_FEATURES_AFTER_SELECTION,
FEATURE_CORRELATION_THRESHOLD, and MIN_CANDLES_FOR_INDICATORS so feature_selection,
training_validation, config,
signal generation (worker + use case + API), and training pipelines stay in sync.
"""

from __future__ import annotations

# Default cap on number of features after selection (ADR-014).
# Prevents overfitting when 71+ features are available.
DEFAULT_MAX_FEATURES: int = 25

# Hard upper bound on a user-requested max_features (API validation + FE input/hint).
# WHY 50 (not 200): overfitting guard tied to events-per-variable. On 4h the minority
# class (BUY/SELL) has ~300 samples, so 50 features ≈ 6 EPV (the aggressive edge of the
# classic >=10-EPV rule); 100 would be ~3 EPV (overfit). Empirically the 4-stage selection
# self-selects ~14 features, so this cap never binds the model's own choice — it only
# stops a manual request for an overfit count. Mirrored in @pulsai/shared (FE SoT).
MAX_FEATURES_LIMIT: int = 50

# PLAN_SOL_SWITCH 13.29 (FEATURE-COUNT): the counts a fit may choose between on its own training folds
# (train_model_feature_count), all inside MAX_FEATURES_LIMIT; the 4-stage selection is recorded to keep ~14 on its own.
FEATURE_COUNT_CANDIDATES: tuple[int, ...] = (10, 15, 25, 50)
# The search's default for every training door (CLI and /training/new): OFF until 13.29's paired grade shows the in-fit
# count beats the fixed max_features; flipping it means setting this to FEATURE_COUNT_CANDIDATES, with that record cited.
DEFAULT_FEATURE_COUNTS: tuple[int, ...] = ()

# Floor on how many features to keep when L1/RF shrink the set too far (regression: 5m collapse to 1).
# Effective count per run is min(this, max_features, columns available after correlation removal).
DEFAULT_MIN_FEATURES_AFTER_SELECTION: int = 3

# Correlation threshold for removing highly correlated feature pairs (inter-feature).
# Tighter than v11's 0.95; 0.85 reduces redundancy while keeping signal.
FEATURE_CORRELATION_THRESHOLD: float = 0.85

# Minimum OHLCV candles required for indicator warmup and signal generation.
# WHY 100: EMA-50 needs 50 periods, RSI-14 needs 15+, ADX 28+; 100 gives safety margin.
# SoT: generate_signals task, GenerateSignalUseCase, signals_deps, API signals endpoint.
MIN_CANDLES_FOR_INDICATORS: int = 100

# Minimum valid rows after feature calculation + clean for ML backtest predictions.
# WHY same as MIN_CANDLES_FOR_INDICATORS: backtest needs the same warmup as live signals.
# When zero rows remain after drop_nulls, we raise instead of returning all-HOLD (misleading).
MIN_CANDLES_FOR_BACKTEST: int = 100

# Trading-bots parity: close delta threshold for is_high_velocity flag.
HIGH_VELOCITY_DELTA_THRESHOLD: float = 100.0

# RiskMetrics-style EWMA volatility (λ=0.94 → column ``ewma_vol_94``). Research parity: nonprice vol_fwd SCOUT.
EWMA_VOL_LAMBDA_DEFAULT: float = 0.94
EWMA_VOL_FEATURE_COLUMN: str = "ewma_vol_94"

__all__ = [
    "DEFAULT_FEATURE_COUNTS",
    "DEFAULT_MAX_FEATURES",
    "DEFAULT_MIN_FEATURES_AFTER_SELECTION",
    "EWMA_VOL_FEATURE_COLUMN",
    "EWMA_VOL_LAMBDA_DEFAULT",
    "FEATURE_CORRELATION_THRESHOLD",
    "FEATURE_COUNT_CANDIDATES",
    "HIGH_VELOCITY_DELTA_THRESHOLD",
    "MAX_FEATURES_LIMIT",
    "MIN_CANDLES_FOR_BACKTEST",
    "MIN_CANDLES_FOR_INDICATORS",
]
