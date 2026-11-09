"""Parser support for multi-target Conclusion lines.

Single-target (existing, unchanged): ``Conclusion: BUY 80% target $1000 est``
Multi-target (new): ``Conclusion: BUY 80% targets $1000 / $1050 / $1100 est``

Contract:
- ``ExplainConclusion.target_price`` always holds the FIRST (nearest) target —
  preserves backwards compatibility for any consumer that only reads
  ``target_price``.
- ``ExplainConclusion.targets`` holds the full ordered list when the LLM emits
  the multi-target form; ``None`` otherwise so the FE can branch cheaply.

The parser must accept both forms. Order in the list is the order in the line
(nearest → farthest, by LLM convention).
"""

from __future__ import annotations

from src.infrastructure.ai.explain_conclusion_parser import parse_conclusion_from_explanation


def test_parses_single_target_form_unchanged() -> None:
    """Existing single-target form: targets is None, target_price is the single value."""
    text = "Body line.\nConclusion: BUY 80% target $1234.56 est"
    result = parse_conclusion_from_explanation(text)
    assert result is not None
    assert result.action.value == "BUY"
    assert result.confidence_pct == 80
    assert result.target_price == 1234.56
    assert result.targets is None


def test_parses_multi_target_form_three_targets() -> None:
    """``targets $A / $B / $C`` form populates the full list."""
    text = "Body line.\nConclusion: BUY 80% targets $1000 / $1050 / $1100 est"
    result = parse_conclusion_from_explanation(text)
    assert result is not None
    assert result.action.value == "BUY"
    assert result.confidence_pct == 80
    assert result.targets == [1000.0, 1050.0, 1100.0]
    # target_price mirrors the first entry for backwards compatibility.
    assert result.target_price == 1000.0


def test_parses_multi_target_form_two_targets() -> None:
    """Two-target form is allowed (some signals only have 2 levels)."""
    text = "Conclusion: SELL 65% targets $50,000 / $48,500 est"
    result = parse_conclusion_from_explanation(text)
    assert result is not None
    assert result.action.value == "SELL"
    assert result.targets == [50_000.0, 48_500.0]
    assert result.target_price == 50_000.0


def test_multi_target_accepts_no_trailing_est() -> None:
    """Trailing ``est`` qualifier is optional (LLM may drop it)."""
    text = "Conclusion: BUY 70% targets $100 / $105 / $110"
    result = parse_conclusion_from_explanation(text)
    assert result is not None
    assert result.targets == [100.0, 105.0, 110.0]


def test_malformed_multi_target_returns_none() -> None:
    """Trailing comma / dangling slash should NOT parse."""
    text = "Conclusion: BUY 80% targets $100 / / $110 est"
    result = parse_conclusion_from_explanation(text)
    assert result is None


def test_parser_skips_conclusion_substring_inside_body_lines() -> None:
    """Regression: a body line containing the word "Conclusion:" must not false-match.

    The parser walks lines bottom-up looking for a "Conclusion:" prefix. A body
    bullet that quotes the word (e.g. "- Conclusion: see Section 3 below") must
    NOT be returned as the parsed conclusion — only a properly-formatted line
    matching the grammar wins.
    """
    text = "Body discussing the signal.\n- Conclusion: see the appendix for derivation\nConclusion: BUY 80% target $1000 est"
    result = parse_conclusion_from_explanation(text)
    # The terminal canonical line wins; the prose mention earlier is ignored.
    assert result is not None
    assert result.action.value == "BUY"
    assert result.target_price == 1000.0


def test_parser_returns_none_when_only_prose_conclusion_exists() -> None:
    """A free-text 'Conclusion:' without the structured grammar must NOT parse."""
    text = "Body discussing the signal.\nConclusion: this trade is uncertain — wait for confirmation."
    result = parse_conclusion_from_explanation(text)
    assert result is None
