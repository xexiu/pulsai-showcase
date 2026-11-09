"""Tests: EXIT_STRATEGY_FIELD_KEYS stays aligned with backtester ATR usage."""

from __future__ import annotations

from src.infrastructure.ml.backtester_types import ExitStrategy
from src.infrastructure.ml.exit_strategy_metadata import EXIT_STRATEGY_FIELD_KEYS


def test_atr_based_field_keys_include_sl_cap_and_risk_reward() -> None:
    """ATR exits use max_sl_pct cap and risk_reward_ratio for TP; metadata must expose them."""
    keys = EXIT_STRATEGY_FIELD_KEYS[ExitStrategy.ATR_BASED]
    assert "atr_period" in keys
    assert "atr_multiplier" in keys
    assert "max_sl_pct" in keys
    assert "risk_reward_ratio" in keys


def test_dynamic_tpsl_reuses_atr_parameter_contract() -> None:
    """Dynamic TP/SL should expose the same volatility controls as ATR-based exits."""
    keys = EXIT_STRATEGY_FIELD_KEYS[ExitStrategy.DYNAMIC_TPSL]
    assert "atr_period" in keys
    assert "atr_multiplier" in keys
    assert "max_sl_pct" in keys
    assert "risk_reward_ratio" in keys
