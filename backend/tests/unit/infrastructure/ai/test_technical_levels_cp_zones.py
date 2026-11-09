"""Technical-levels RAG block: chart-pattern (CP) zones rendering.

Pins that CP support / resistance / target / stop-loss (absolute prices from
the double-bottom / double-top detector) render as labeled lines inside the
technical_levels section.

WHY add CP zones: ``dist_to_resistance_20`` and ``dist_to_support_20`` are
proximity metrics to 20-period pivot levels — they're NOT the same as CP
levels (geometric entry/target prices from confirmed pattern legs). Both
give the LLM independent views of where price could go.
"""

from __future__ import annotations

from src.infrastructure.ai.rag_explain_technical_levels import format_technical_levels_block
from src.shared.constants.ai_explain_conclusion import TECHNICAL_LEVEL_FEATURE_KEYS


def test_cp_resistance_line_renders() -> None:
    block = format_technical_levels_block(
        current_price=100.0,
        model_input_features={"cp_resistance_line": 105.0},
        action="BUY",
    )
    assert block is not None
    assert "CP resistance (chart pattern): ~$105.00" in block
    assert "+5.00%" in block


def test_cp_support_line_renders() -> None:
    block = format_technical_levels_block(
        current_price=100.0,
        model_input_features={"cp_support_line": 95.0},
        action="SELL",
    )
    assert block is not None
    assert "CP support (chart pattern): ~$95.00" in block
    assert "-5.00%" in block


def test_cp_target_and_stop_loss_render() -> None:
    block = format_technical_levels_block(
        current_price=50_000.0,
        model_input_features={"cp_target": 53_000.0, "cp_stop_loss": 48_500.0},
        action="BUY",
    )
    assert block is not None
    assert "CP target (pattern measured move)" in block
    assert "CP stop-loss (pattern invalidation)" in block


def test_cp_keys_in_feature_keys_constant() -> None:
    """Keys in the public SoT allowlist so admin/feature-config surfaces see them."""
    for expected in ("cp_resistance_line", "cp_support_line", "cp_target", "cp_stop_loss"):
        assert expected in TECHNICAL_LEVEL_FEATURE_KEYS, expected


def test_cp_levels_render_alongside_dist_to_and_keltner() -> None:
    """All three families coexist in one block — no mutual exclusion."""
    block = format_technical_levels_block(
        current_price=100.0,
        model_input_features={
            "dist_to_resistance_5": -1.5,
            "keltner_upper": 103.0,
            "cp_resistance_line": 105.0,
            "cp_target": 110.0,
        },
        action="BUY",
    )
    assert block is not None
    assert "Nearest resistance" in block
    assert "Keltner upper" in block
    assert "CP resistance" in block
    assert "CP target" in block
