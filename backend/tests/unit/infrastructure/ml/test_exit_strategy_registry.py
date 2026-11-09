"""Behavior tests for the exit-strategy SoT registry (Fix 4-core).

Guards the single-source invariant: field NAMES are derived from the defaults map (so they can't
drift), and every default references a shared constant (not a re-hardcoded literal). This is what
lets BE call sites + the config endpoint + both FE registries share one source.
"""

from __future__ import annotations

from src.infrastructure.ml.backtester_types import ExitStrategy
from src.infrastructure.ml.exit_strategy_metadata import (
    EXIT_STRATEGY_FIELD_DEFAULTS,
    EXIT_STRATEGY_FIELD_KEYS,
    get_exit_strategy_field_defaults,
    get_exit_strategy_field_keys,
)
from src.shared.constants.backtest import (
    DEFAULT_BACKTEST_ATR_MULTIPLIER,
    DEFAULT_BACKTEST_ATR_PERIOD,
    DEFAULT_BACKTEST_RISK_REWARD_RATIO,
    DEFAULT_BACKTEST_TRAIL_ACTIVATION_PCT,
    DEFAULT_BACKTEST_TRAIL_PCT,
)


def test_every_strategy_has_a_defaults_entry() -> None:
    for strategy in ExitStrategy:
        assert strategy in EXIT_STRATEGY_FIELD_DEFAULTS


def test_field_keys_are_derived_from_defaults() -> None:
    # Single SoT: names == the defaults' fields, in order (no dual-dict drift possible).
    for strategy in ExitStrategy:
        assert EXIT_STRATEGY_FIELD_KEYS[strategy] == tuple(EXIT_STRATEGY_FIELD_DEFAULTS[strategy].keys())
    assert EXIT_STRATEGY_FIELD_KEYS[ExitStrategy.FIXED_TPSL] == ("stop_loss_pct", "take_profit_pct")
    assert EXIT_STRATEGY_FIELD_KEYS[ExitStrategy.TRAILING_STOP] == ("stop_loss_pct", "trail_activation_pct", "trail_pct")


def test_defaults_reference_shared_constants_not_literals() -> None:
    assert EXIT_STRATEGY_FIELD_DEFAULTS[ExitStrategy.RISK_REWARD]["risk_reward_ratio"] == DEFAULT_BACKTEST_RISK_REWARD_RATIO
    trailing = EXIT_STRATEGY_FIELD_DEFAULTS[ExitStrategy.TRAILING_STOP]
    assert trailing["trail_pct"] == DEFAULT_BACKTEST_TRAIL_PCT
    assert trailing["trail_activation_pct"] == DEFAULT_BACKTEST_TRAIL_ACTIVATION_PCT
    atr = EXIT_STRATEGY_FIELD_DEFAULTS[ExitStrategy.ATR_BASED]
    assert atr["atr_period"] == DEFAULT_BACKTEST_ATR_PERIOD
    assert atr["atr_multiplier"] == DEFAULT_BACKTEST_ATR_MULTIPLIER


def test_stop_loss_and_take_profit_have_no_universal_default() -> None:
    fixed = EXIT_STRATEGY_FIELD_DEFAULTS[ExitStrategy.FIXED_TPSL]
    assert fixed["stop_loss_pct"] is None
    assert fixed["take_profit_pct"] is None


def test_accessors_are_string_keyed_and_agree() -> None:
    keys = get_exit_strategy_field_keys()
    defaults = get_exit_strategy_field_defaults()
    strategy_values = {s.value for s in ExitStrategy}
    assert set(keys) == strategy_values
    assert set(defaults) == strategy_values
    for strategy, fields in keys.items():
        assert list(defaults[strategy].keys()) == fields
