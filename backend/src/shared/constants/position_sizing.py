"""Position sizing mode constants for ML/classic backtests (Sprint 3.1c)."""

from __future__ import annotations

# Equal split / explicit sizing (legacy): initial_capital / max_open_positions or explicit size.
POSITION_SIZING_MODE_EQUAL: str = "equal"

# Kelly criterion from closed-trade stats (capped fraction of available balance).
POSITION_SIZING_MODE_KELLY: str = "kelly"

# Risk budget divided by ATR% at entry (inverse-vol scaling).
POSITION_SIZING_MODE_VOLATILITY_SCALED: str = "volatility_scaled"

# Reduce notional as drawdown from peak equity deepens.
POSITION_SIZING_MODE_DRAWDOWN_SCALED: str = "drawdown_scaled"

# Inverse-vol sizing using regressor-predicted range on 1h-8h when ratios supplied (Lane C).
POSITION_SIZING_MODE_REGRESSOR_VOL_SCALED: str = "regressor_vol_scaled"

# Risk a fixed fraction of CURRENT equity at the trade's own stop, capped at leverage x equity -- the risk-sized book's
# one rule (domain risk_sized_book.risk_sized_notional; BACKTEST-ONE S2b).
POSITION_SIZING_MODE_RISK_SIZED: str = "risk_sized"

# The owner's account: margin = a fraction of CURRENT equity, notional = that margin x the lane's leverage -- the margin
# account's one rule (domain position_sizing.margin_fraction.fractional_margin; BACKTEST-ONE S2c).
POSITION_SIZING_MODE_MARGIN_FRACTION: str = "margin_fraction"

# Owner, 2026-10-09: "$20 -> $2, $28 -> $2.80, $1000 -> $100" -- 10 % of the equity before the trade, continuous.
DEFAULT_MARGIN_FRACTION: float = 0.10

# Mid-band TFs where regressor range beats ATR incrementally (regressor_edge FINDINGS).
# Include 12h for promoted overlay ridge sizing hosts.
REGRESSOR_VOL_SIZING_TIMEFRAMES: frozenset[str] = frozenset({"1h", "4h", "8h", "12h"})

POSITION_SIZING_MODES: frozenset[str] = frozenset(
    {
        POSITION_SIZING_MODE_EQUAL,
        POSITION_SIZING_MODE_KELLY,
        POSITION_SIZING_MODE_VOLATILITY_SCALED,
        POSITION_SIZING_MODE_DRAWDOWN_SCALED,
        POSITION_SIZING_MODE_REGRESSOR_VOL_SCALED,
        POSITION_SIZING_MODE_RISK_SIZED,
        POSITION_SIZING_MODE_MARGIN_FRACTION,
    },
)

DEFAULT_KELLY_FRACTION_CAP: float = 0.25
DEFAULT_VOL_SIZING_TARGET_RISK_PCT: float = 0.01
DEFAULT_VOL_SIZING_MAX_FRACTION_OF_BALANCE: float = 1.0

# Drawdown bands: (max_drawdown_pct, scale_factor). First match wins (ascending dd).
DEFAULT_DRAWDOWN_SCALE_RULES: tuple[tuple[float, float], ...] = (
    (0.10, 1.0),
    (0.20, 0.5),
    (1.0, 0.25),
)

MIN_BARS_FOR_BETA_REGRESSION: int = 8

# Regime-stratified Kelly: minimum closed trades in the same regime bucket before
# trusting bucket-only stats (else fall back to global closed trades). See REGIME_STRATIFIED_KELLY_SPEC.md.
DEFAULT_MIN_KELLY_TRADES_PER_REGIME: int = 5
