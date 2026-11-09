"""Mock provider body augmentation: surface RAG sections in mock output.

The mock provider's hardcoded ``MOCK_EXPLANATIONS`` templates do not reference
the rendered RAG sections (technical levels, position sizing). Without
augmentation, the user-visible modal in mock mode never shows those sections —
they only exist in the LLM prompt context. This test pins the contract: the
mock provider MUST surface those rendered blocks in its response body so dev
mode has visual parity with what a real LLM would write.

These tests fail BEFORE the augmentation lands (RED step in TDD).
"""

from __future__ import annotations

import pytest

from src.infrastructure.ai.ai_provider_mock import MockAIProvider


@pytest.fixture
def mock_provider() -> MockAIProvider:
    return MockAIProvider()


def _hold_context_with_levels_and_sizing() -> str:
    """A realistic mock RAG context excerpt — HOLD signal, levels + sizing present."""
    return (
        "## Trading Signal\n"
        "- Action: HOLD\n"
        "- Confidence: 76%\n"
        "- Symbol: BTC/USDT\n"
        "- Price at signal time: $77,454.26\n"
        "\n"
        "## Technical levels (action-anchored targets)\n"
        "- Snapshot price: $77,454.26\n"
        "- Nearest resistance (5-bar): ~$78,225.11 (+1.00% from price)\n"
        "- Nearest support (5-bar): ~$76,683.41 (-1.00% from price)\n"
        "- HOLD target rule: cite the current snapshot price (no directional target).\n"
        "\n"
        "## Position sizing (illustrative Kelly-style hint)\n"
        "- Suggested fraction of capital (confidence-only half-Kelly proxy): 5.00%\n"
        "- Worked example: 5.00% of a $1,000 reference capital = $50.00 position.\n"
        "- Not personal advice; not based on your account or trade history.\n"
        "\n"
        "## Some other section after sizing\n"
        "- Should NOT appear in the augmented body.\n"
    )


@pytest.mark.asyncio
async def test_mock_body_contains_technical_levels_when_in_context(
    mock_provider: MockAIProvider,
) -> None:
    """Mock body must include the rendered ``## Technical levels`` block."""
    context = _hold_context_with_levels_and_sizing()
    response = await mock_provider.explain_signal(context, language="en")

    assert "## Technical levels" in response
    assert "Nearest resistance" in response
    assert "Nearest support" in response


@pytest.mark.asyncio
async def test_mock_body_contains_position_sizing_when_in_context(
    mock_provider: MockAIProvider,
) -> None:
    """Mock body must include the rendered ``## Position sizing`` block."""
    context = _hold_context_with_levels_and_sizing()
    response = await mock_provider.explain_signal(context, language="en")

    assert "## Position sizing" in response
    assert "Worked example" in response
    assert "$1,000 reference capital" in response


@pytest.mark.asyncio
async def test_mock_body_does_not_leak_other_sections(
    mock_provider: MockAIProvider,
) -> None:
    """Only the two whitelisted sections are appended; nothing else."""
    context = _hold_context_with_levels_and_sizing()
    response = await mock_provider.explain_signal(context, language="en")

    assert "## Some other section after sizing" not in response


@pytest.mark.asyncio
async def test_mock_body_appended_before_conclusion_line(
    mock_provider: MockAIProvider,
) -> None:
    """Augmented blocks must precede the ``Conclusion:`` line — that is the contract.

    The Conclusion line must remain the LAST line of the body before the disclaimer
    so the BE parser (``parse_conclusion_from_explanation``) keeps working.
    """
    context = _hold_context_with_levels_and_sizing()
    response = await mock_provider.explain_signal(context, language="en")

    sizing_idx = response.find("## Position sizing")
    levels_idx = response.find("## Technical levels")
    conclusion_idx = response.find("Conclusion:")

    assert levels_idx > 0
    assert sizing_idx > 0
    assert conclusion_idx > 0
    assert levels_idx < conclusion_idx
    assert sizing_idx < conclusion_idx


@pytest.mark.asyncio
async def test_mock_body_unchanged_when_no_extra_sections_in_context(
    mock_provider: MockAIProvider,
) -> None:
    """When the context has no extra sections, mock body must NOT contain spurious headers."""
    context = "## Trading Signal\n- Action: HOLD\n- Confidence: 50%\n- Price at signal time: $100.00\n"
    response = await mock_provider.explain_signal(context, language="en")

    assert "## Technical levels" not in response
    assert "## Position sizing" not in response
    # Conclusion line must still be present.
    assert "Conclusion: HOLD" in response


@pytest.mark.asyncio
async def test_mock_body_for_buy_includes_levels(
    mock_provider: MockAIProvider,
) -> None:
    """BUY context with technical levels — body should contain the section."""
    context = (
        "## Trading Signal\n"
        "- Action: BUY\n"
        "- Confidence: 80%\n"
        "- Price at signal time: $100.00\n"
        "\n"
        "## Technical levels (action-anchored targets)\n"
        "- Snapshot price: $100.00\n"
        "- Nearest resistance (5-bar): ~$103.00 (+3.00% from price)\n"
        "- BUY target rule: cite the nearest resistance level above as the Conclusion target.\n"
    )
    response = await mock_provider.explain_signal(context, language="en")

    assert "## Technical levels" in response
    assert "Nearest resistance" in response
    assert "Conclusion: BUY" in response
