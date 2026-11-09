"""SoT for live vs backtest ML feature-path parity tests (pinned OHLCV fixtures)."""

from __future__ import annotations

from typing import Final

# Small model-column subset exercised on every alignment-TF recorded fixture.
# Chosen for stability (continuous + zone) without chart-marker-only columns.
ML_INFERENCE_PARITY_FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    "rsi_14",
    "gr_zone",
    "macd",
    "bb_upper",
    "bb_lower",
)

# Last-bar live vs backtest feature dicts must match within this ε (float noise).
ML_INFERENCE_PARITY_MAX_ABS_DELTA: Final[float] = 1e-6

# Live tail length when slicing recorded mega-window (matches inference SoT).
ML_INFERENCE_PARITY_LIVE_TAIL_LIMIT: Final[int] = 500

# Backtest parity lookback (days) for window suffix tests — matches inference-compare default.
ML_INFERENCE_PARITY_LOOKBACK_DAYS: Final[int] = 30
