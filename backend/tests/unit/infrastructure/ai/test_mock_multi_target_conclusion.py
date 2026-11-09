"""Mock provider emits the multi-target Conclusion form when levels are stacked.

Contract:
- BUY/SELL: emit ``Conclusion: ACTION C% targets $T1 / $T2 / $T3 est`` when
  the rendered RAG context exposes 2+ usable resistance/support levels
  (nearest 5/20-bar from ``dist_to_*`` + optional Keltner band).
- HOLD: ALWAYS single-target ``Conclusion: HOLD C% target $X est``.
- BUY/SELL with only ONE level present → fall back to single-target form.
- The first ``targets`` value matches the nearest level (T1 = nearest resistance
  for BUY, nearest support for SELL) so the parser's ``target_price`` field
  stays backwards-compatible.
"""

from __future__ import annotations

import pytest

from src.infrastructure.ai.ai_provider_mock import MockAIProvider
from src.infrastructure.ai.explain_conclusion_parser import parse_conclusion_from_explanation


@pytest.fixture
def mock_provider() -> MockAIProvider:
    return MockAIProvider()


def _buy_context_three_levels() -> str:
    return (
        "## Trading Signal\n"
        "- Action: BUY\n"
        "- Confidence: 82%\n"
        "- Price at signal time: $100.00\n"
        "\n"
        "## Technical levels (action-anchored targets)\n"
        "- Snapshot price: $100.00\n"
        "- Nearest resistance (5-bar): ~$102.00 (+2.00% from price)\n"
        "- Nearest resistance (20-bar): ~$105.50 (+5.50% from price)\n"
        "- Keltner upper (ATR-anchored resistance): ~$108.00 (+8.00% from price)\n"
    )


def _sell_context_two_levels() -> str:
    return (
        "## Trading Signal\n"
        "- Action: SELL\n"
        "- Confidence: 70%\n"
        "- Price at signal time: $50,000.00\n"
        "\n"
        "## Technical levels (action-anchored targets)\n"
        "- Snapshot price: $50,000.00\n"
        "- Nearest support (5-bar): ~$48,500.00 (-3.00% from price)\n"
        "- Keltner lower (ATR-anchored support): ~$47,000.00 (-6.00% from price)\n"
    )


def _hold_context_with_levels() -> str:
    return (
        "## Trading Signal\n"
        "- Action: HOLD\n"
        "- Confidence: 60%\n"
        "- Price at signal time: $77,454.26\n"
        "\n"
        "## Technical levels (action-anchored targets)\n"
        "- Snapshot price: $77,454.26\n"
        "- Nearest resistance (5-bar): ~$78,225.11 (+1.00% from price)\n"
        "- Nearest support (5-bar): ~$76,683.41 (-1.00% from price)\n"
    )


def _buy_context_single_level() -> str:
    return (
        "## Trading Signal\n"
        "- Action: BUY\n"
        "- Confidence: 65%\n"
        "- Price at signal time: $100.00\n"
        "\n"
        "## Technical levels (action-anchored targets)\n"
        "- Snapshot price: $100.00\n"
        "- Nearest resistance (5-bar): ~$102.00 (+2.00% from price)\n"
    )


@pytest.mark.asyncio
async def test_buy_three_levels_emits_multi_target(mock_provider: MockAIProvider) -> None:
    """BUY with 5-bar + 20-bar + Keltner → all three render as ``targets``."""
    response = await mock_provider.explain_signal(_buy_context_three_levels(), language="en")
    assert "targets $102.00 / $105.50 / $108.00 est" in response
    parsed = parse_conclusion_from_explanation(response)
    assert parsed is not None
    assert parsed.action.value == "BUY"
    assert parsed.targets == [102.0, 105.5, 108.0]
    assert parsed.target_price == 102.0


@pytest.mark.asyncio
async def test_sell_two_levels_emits_multi_target(mock_provider: MockAIProvider) -> None:
    """SELL with one dist_to_support + Keltner lower → multi-target with 2 entries."""
    response = await mock_provider.explain_signal(_sell_context_two_levels(), language="en")
    assert "targets $48500.00 / $47000.00 est" in response
    parsed = parse_conclusion_from_explanation(response)
    assert parsed is not None
    assert parsed.action.value == "SELL"
    assert parsed.targets == [48_500.0, 47_000.0]


@pytest.mark.asyncio
async def test_hold_always_single_target(mock_provider: MockAIProvider) -> None:
    """HOLD never uses multi-target — even when multiple levels are visible."""
    response = await mock_provider.explain_signal(_hold_context_with_levels(), language="en")
    assert "targets " not in response.lower()
    assert "target $77454.26 est" in response
    parsed = parse_conclusion_from_explanation(response)
    assert parsed is not None
    assert parsed.action.value == "HOLD"
    assert parsed.targets is None


@pytest.mark.asyncio
async def test_buy_single_level_falls_back_to_single_target(mock_provider: MockAIProvider) -> None:
    """Only one usable resistance → keep single-target form (no spurious slash)."""
    response = await mock_provider.explain_signal(_buy_context_single_level(), language="en")
    assert " targets " not in response
    assert "target $102.00 est" in response
