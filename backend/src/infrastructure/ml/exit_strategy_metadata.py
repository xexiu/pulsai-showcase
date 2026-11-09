"""SoT for exit-strategy parameters: which fields each strategy uses AND their defaults.

WHY here:
- The backtester ``ExitStrategy`` enum owns the available strategies.
- The public config endpoint needs BE-driven parameter metadata (names AND defaults).
- The FE must not maintain a parallel strategy -> params/defaults registry (it consumes this).

``EXIT_STRATEGY_FIELD_DEFAULTS`` is the single source; ``EXIT_STRATEGY_FIELD_KEYS`` is DERIVED
from it, so field names and defaults can never drift apart. ``stop_loss_pct`` / ``take_profit_pct``
have no universal default (caller-supplied) -> ``None``. Field ORDER within a strategy is the FE
render order; dict insertion order preserves it.
"""

from __future__ import annotations

from src.infrastructure.ml.backtester_types import ExitStrategy
from src.shared.constants.backtest import (
    DEFAULT_BACKTEST_ATR_MULTIPLIER,
    DEFAULT_BACKTEST_ATR_PERIOD,
    DEFAULT_BACKTEST_MAX_SL_PCT,
    DEFAULT_BACKTEST_MIN_NET_PCT,
    DEFAULT_BACKTEST_RISK_REWARD_RATIO,
    DEFAULT_BACKTEST_TRAIL_ACTIVATION_PCT,
    DEFAULT_BACKTEST_TRAIL_PCT,
)

EXIT_STRATEGY_FIELD_DEFAULTS: dict[ExitStrategy, dict[str, float | int | None]] = {
    ExitStrategy.FIXED_HOLDING: {},
    ExitStrategy.RAW_SIGNAL: {},
    ExitStrategy.FIXED_TPSL: {"stop_loss_pct": None, "take_profit_pct": None},
    ExitStrategy.RISK_REWARD: {"stop_loss_pct": None, "risk_reward_ratio": DEFAULT_BACKTEST_RISK_REWARD_RATIO},
    ExitStrategy.TRAILING_STOP: {
        "stop_loss_pct": None,
        "trail_activation_pct": DEFAULT_BACKTEST_TRAIL_ACTIVATION_PCT,
        "trail_pct": DEFAULT_BACKTEST_TRAIL_PCT,
    },
    # WHY max_sl_pct + risk_reward_ratio: ATR uses these for the SL cap and TP distance
    # (see check_atr_tpsl_exit in backtester_exits.py).
    ExitStrategy.ATR_BASED: {
        "atr_period": DEFAULT_BACKTEST_ATR_PERIOD,
        "atr_multiplier": DEFAULT_BACKTEST_ATR_MULTIPLIER,
        "max_sl_pct": DEFAULT_BACKTEST_MAX_SL_PCT,
        "risk_reward_ratio": DEFAULT_BACKTEST_RISK_REWARD_RATIO,
    },
    ExitStrategy.DYNAMIC_TPSL: {
        "atr_period": DEFAULT_BACKTEST_ATR_PERIOD,
        "atr_multiplier": DEFAULT_BACKTEST_ATR_MULTIPLIER,
        "max_sl_pct": DEFAULT_BACKTEST_MAX_SL_PCT,
        "risk_reward_ratio": DEFAULT_BACKTEST_RISK_REWARD_RATIO,
    },
    ExitStrategy.PREDICTED_REGRESSOR: {},
    ExitStrategy.MIN_PROFIT_AFTER_FEES: {"min_net_pct": DEFAULT_BACKTEST_MIN_NET_PCT},
    # Research-only: its levers ride the cert grid's hub fields, its stop is the book's own column.
    ExitStrategy.THIN_STOP_LADDER: {},
}

# DERIVED from the defaults SoT above (one source -> field names & defaults can't drift apart).
EXIT_STRATEGY_FIELD_KEYS: dict[ExitStrategy, tuple[str, ...]] = {strategy: tuple(fields) for strategy, fields in EXIT_STRATEGY_FIELD_DEFAULTS.items()}


def get_exit_strategy_field_keys() -> dict[str, list[str]]:
    """Return frontend field keys for every known exit strategy."""
    return {strategy.value: list(EXIT_STRATEGY_FIELD_KEYS.get(strategy, ())) for strategy in ExitStrategy}


def get_exit_strategy_field_defaults() -> dict[str, dict[str, float | int | None]]:
    """Return {strategy: {field: default}} for every exit strategy (BE-served SoT for the FE)."""
    return {strategy.value: dict(EXIT_STRATEGY_FIELD_DEFAULTS.get(strategy, {})) for strategy in ExitStrategy}
