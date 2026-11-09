"""Signal-triggers RAG block: Stochastic crossover, RSI/MACD divergences.

Pin the contract:
- The block renders only when at least one trigger is firing (non-zero).
- ``+1`` is labeled "bullish", ``-1`` is labeled "bearish", ``0`` is omitted.
- Friendly labels come from a SoT map in the formatter module so the prompt
  stays human-readable.
- Keys live in ``SIGNAL_TRIGGER_FEATURE_KEYS`` (SoT) so the admin UI / future
  config surfaces enumerate them consistently with the BE pipeline.
"""

from __future__ import annotations

from src.infrastructure.ai.rag_explain_signal_sections import format_signal_triggers_block
from src.shared.constants.ai_explain_conclusion import SIGNAL_TRIGGER_FEATURE_KEYS


def test_returns_none_when_no_triggers_fire() -> None:
    block = format_signal_triggers_block(
        {
            "signal_stochastic_crossover": 0,
            "rsi_divergence": 0,
            "macd_divergence": 0,
        }
    )
    assert block is None


def test_returns_none_when_features_empty() -> None:
    assert format_signal_triggers_block(None) is None
    assert format_signal_triggers_block({}) is None


def test_renders_bullish_stochastic_crossover() -> None:
    block = format_signal_triggers_block({"signal_stochastic_crossover": 1})
    assert block is not None
    assert "Stochastic crossover (ST)" in block
    assert "bullish" in block
    assert "+1" in block


def test_renders_bearish_macd_divergence() -> None:
    block = format_signal_triggers_block({"macd_divergence": -1})
    assert block is not None
    assert "MACD divergence" in block
    assert "bearish" in block


def test_omits_zero_value_features_alongside_firing_ones() -> None:
    block = format_signal_triggers_block(
        {
            "signal_stochastic_crossover": 1,
            "rsi_divergence": 0,
            "macd_divergence": -1,
        }
    )
    assert block is not None
    assert "Stochastic crossover" in block
    assert "MACD divergence" in block
    assert "RSI divergence" not in block


def test_signal_trigger_keys_are_exposed_as_sot() -> None:
    assert "signal_stochastic_crossover" in SIGNAL_TRIGGER_FEATURE_KEYS
    assert "rsi_divergence" in SIGNAL_TRIGGER_FEATURE_KEYS
    assert "macd_divergence" in SIGNAL_TRIGGER_FEATURE_KEYS
