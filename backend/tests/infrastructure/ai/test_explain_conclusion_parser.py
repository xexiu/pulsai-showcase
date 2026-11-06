"""Behavior tests for the explain-signal Conclusion parser + trimmer.

The parser is the SoT for turning the LLM's terminal `Conclusion:` line into
a typed ExplainConclusion. The trimmer keeps total line count under
EXPLAIN_MAX_LINES while preserving the Conclusion.
"""

from __future__ import annotations

import pytest

from src.api.v1.endpoints.ai_schemas import ConclusionAction
from src.infrastructure.ai.explain_conclusion_parser import (
    parse_conclusion_from_explanation,
    trim_explanation_to_max_lines,
)
from src.shared.constants.ai_explain_conclusion import EXPLAIN_MAX_LINES


class TestParseConclusion:
    def test_parses_canonical_buy_line(self) -> None:
        text = "Body sentence.\nConclusion: BUY 88% target $50,000 est"
        result = parse_conclusion_from_explanation(text)
        assert result is not None
        assert result.action == ConclusionAction.BUY
        assert result.confidence_pct == 88
        assert result.target_price == 50000.0

    def test_parses_sell_with_decimal_price(self) -> None:
        text = "stuff\nConclusion: SELL 73% target $1,234.56 est"
        result = parse_conclusion_from_explanation(text)
        assert result is not None
        assert result.action == ConclusionAction.SELL
        assert result.confidence_pct == 73
        assert result.target_price == pytest.approx(1234.56)

    def test_parses_hold_without_trailing_est(self) -> None:
        text = "Conclusion: HOLD 50% target $42000"
        result = parse_conclusion_from_explanation(text)
        assert result is not None
        assert result.action == ConclusionAction.HOLD

    def test_is_case_insensitive_on_action(self) -> None:
        text = "Conclusion: buy 80% target $30000 est"
        result = parse_conclusion_from_explanation(text)
        assert result is not None
        assert result.action == ConclusionAction.BUY

    def test_returns_none_on_empty_text(self) -> None:
        assert parse_conclusion_from_explanation("") is None
        assert parse_conclusion_from_explanation("   ") is None

    def test_returns_none_when_no_conclusion_line(self) -> None:
        text = "First sentence.\nSecond sentence with no verdict."
        assert parse_conclusion_from_explanation(text) is None

    def test_returns_none_when_line_present_but_malformed(self) -> None:
        # Missing percent + target marker.
        assert parse_conclusion_from_explanation("Conclusion: BUY at 50000") is None
        # Confidence out of range (>100) — Pydantic ge/le rejects.
        assert parse_conclusion_from_explanation("Conclusion: BUY 150% target $50000") is None
        # Bad action vocab.
        assert parse_conclusion_from_explanation("Conclusion: MAYBE 50% target $50000") is None

    def test_returns_none_when_target_price_zero(self) -> None:
        # Zero would pass regex but Pydantic gt=0 must reject.
        assert parse_conclusion_from_explanation("Conclusion: BUY 50% target $0") is None

    def test_ignores_trailing_blank_lines_after_conclusion(self) -> None:
        text = "Body line.\nConclusion: BUY 65% target $30000 est\n\n   \n"
        result = parse_conclusion_from_explanation(text)
        assert result is not None
        assert result.confidence_pct == 65


class TestTrimExplanation:
    def test_returns_text_unchanged_when_under_limit(self) -> None:
        text = "line1\nline2\nConclusion: BUY 80% target $1000 est"
        assert trim_explanation_to_max_lines(text) == text

    def test_clamps_long_text_and_preserves_conclusion(self) -> None:
        # Need more body lines than EXPLAIN_MAX_LINES to actually trigger trim.
        body_lines = [f"line {i}" for i in range(EXPLAIN_MAX_LINES + 10)]
        text = "\n".join(body_lines) + "\nConclusion: SELL 70% target $9000 est"
        trimmed = trim_explanation_to_max_lines(text)
        lines = trimmed.splitlines()
        assert len(lines) == EXPLAIN_MAX_LINES
        assert lines[-1].startswith("Conclusion:")
        # Body kept first (max_lines - 1) lines.
        assert lines[0] == "line 0"

    def test_truncates_when_no_conclusion_present(self) -> None:
        body_lines = [f"line {i}" for i in range(EXPLAIN_MAX_LINES + 5)]
        text = "\n".join(body_lines)
        trimmed = trim_explanation_to_max_lines(text)
        lines = trimmed.splitlines()
        assert len(lines) == EXPLAIN_MAX_LINES

    def test_empty_text_returns_empty(self) -> None:
        assert trim_explanation_to_max_lines("") == ""

    def test_respects_custom_max_lines(self) -> None:
        body_lines = [f"line {i}" for i in range(10)]
        text = "\n".join(body_lines) + "\nConclusion: HOLD 50% target $100"
        trimmed = trim_explanation_to_max_lines(text, max_lines=3)
        lines = trimmed.splitlines()
        assert len(lines) == 3
        assert lines[-1].startswith("Conclusion:")
