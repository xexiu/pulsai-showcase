"""Technical-levels RAG block: Keltner upper/lower rendering.

Pin the contract: when ``model_input_features`` carries ``keltner_upper`` /
``keltner_lower`` (absolute prices from the ATR-anchored EMA bands), they
must appear in the rendered block as additional resistance/support lines.

WHY add Keltner alongside the existing ``dist_to_*`` levels:
- ``dist_to_support_N`` / ``dist_to_resistance_N`` come from S/R detection
  on close-only swing lookbacks. Tight/recent-range targets.
- Keltner upper/lower are ATR-anchored EMA bands. In trending regimes they
  produce wider, more breakout-friendly targets than std-dev BB bands.
Giving the LLM both lets it cite whichever level the data supports.
"""

from __future__ import annotations

from src.infrastructure.ai.rag_explain_technical_levels import format_technical_levels_block


def test_keltner_upper_renders_as_resistance_line() -> None:
    """``keltner_upper`` (absolute price) becomes a labeled resistance line."""
    block = format_technical_levels_block(
        current_price=77_454.26,
        model_input_features={"keltner_upper": 78_900.50},
        action="BUY",
    )
    assert block is not None
    assert "Keltner upper" in block
    assert "$78,900.50" in block
    # Offset sign convention: upper above price → positive.
    assert "+1." in block or "+2." in block or "+3." in block


def test_keltner_lower_renders_as_support_line() -> None:
    """``keltner_lower`` (absolute price) becomes a labeled support line."""
    block = format_technical_levels_block(
        current_price=77_454.26,
        model_input_features={"keltner_lower": 76_100.00},
        action="SELL",
    )
    assert block is not None
    assert "Keltner lower" in block
    assert "$76,100.00" in block
    # Offset sign convention: lower below price → negative.
    assert "-1." in block or "-2." in block or "-3." in block


def test_keltner_renders_alongside_dist_to_levels() -> None:
    """Both legacy dist_to_* and Keltner bands render in the same block."""
    block = format_technical_levels_block(
        current_price=100.0,
        model_input_features={
            "dist_to_resistance_5": -1.5,
            "dist_to_support_5": 2.0,
            "keltner_upper": 103.0,
            "keltner_lower": 97.0,
        },
        action="BUY",
    )
    assert block is not None
    assert "Nearest resistance" in block
    assert "Nearest support" in block
    assert "Keltner upper" in block
    assert "Keltner lower" in block


def test_keltner_only_block_renders_when_dist_levels_absent() -> None:
    """When only Keltner is present (no dist_to_*), the block still renders.

    Pins that the new keys alone qualify as "have data" for the section
    so a model trained without dist_to_* still produces a useful prompt.
    """
    block = format_technical_levels_block(
        current_price=50_000.0,
        model_input_features={"keltner_upper": 51_500.0, "keltner_lower": 48_500.0},
        action="HOLD",
    )
    assert block is not None
    assert "Snapshot price" in block
    assert "Keltner upper" in block
    assert "Keltner lower" in block


def test_keltner_keys_in_feature_keys_constant() -> None:
    """Keltner keys must be in the public allowlist constant.

    Without this, an admin-config UI that surfaces "features the AI sees"
    would silently omit Keltner. The constant is the SoT for that surface.
    """
    from src.shared.constants.ai_explain_conclusion import TECHNICAL_LEVEL_FEATURE_KEYS

    assert "keltner_upper" in TECHNICAL_LEVEL_FEATURE_KEYS
    assert "keltner_lower" in TECHNICAL_LEVEL_FEATURE_KEYS
