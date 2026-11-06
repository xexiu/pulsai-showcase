"""
Minimum confidence for ML signal decisions (BUY/SELL vs HOLD).

WHY a dedicated module?
- Product rule: platform default and floor is **50%** (0.50 decimal) everywhere.
- Backtest payloads use 0–100 percent; live / Telegram / use cases use 0–1 decimal.
- Single import avoids drift between settings, Pydantic defaults, and docs.

@see GenerateSignalUseCase confidence thresholding
@see GET /api/v1/config/public limits.min_signal_confidence_percent (FE SoT)
"""  # noqa: RUF002

# Percent (0–100): backtest API, UI sliders, public config.  # noqa: RUF003
DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT: int = 50

# Decimal (0.0–1.0): ML pipeline, Telegram ratio, signal generation.  # noqa: RUF003
DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD: float = DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT / 100.0

# Display: ratio → percent rounding decimals (signal chart JSON, FE tooltips/toasts,
# Telegram NEW SIGNAL / status / explain, signal-alert email).
# SoT for human-visible ML confidence %; keep apps/web `ml-signal-display.ts` in sync.
ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS: int = 1


def confidence_pct_to_threshold(pct: float) -> float:
    """Convert a percent value (0-100) to the decimal threshold (0.0-1.0).

    Mirrors the existing DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD derivation
    pattern so callers never repeat ``pct / 100.0`` inline.

    Args:
        pct: Confidence expressed as a percentage, e.g. 65.0.

    Returns:
        Decimal threshold, e.g. 0.65.
    """
    return pct / 100.0


def format_ml_signal_confidence_percent_display(confidence_0_1: float) -> str:
    """Ratio 0–1 → percent string (chart_json / FE `ml-signal-display` parity)."""  # noqa: RUF002
    d = ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS
    pct = round(float(confidence_0_1) * 100.0, d)
    return f"{pct:.{d}f}%"
