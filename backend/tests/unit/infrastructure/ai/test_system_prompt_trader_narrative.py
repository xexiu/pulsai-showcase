"""SYSTEM_PROMPT contract: trader-narrative rules must mention each feature.

Pins that the LLM prompt covers the new section-specific guidance:
- CP stop-loss → invalidation level
- CP target → cited alongside Conclusion targets
- Position sizing → restate the worked $ example
- Signal triggers → confirm/contradict the headline
- "Tie it together" narrative wrap-up
- Max-lines marker uses the shared constant (no drift)

These tests catch silent regressions when someone edits the prompt template
without realising the new rules underpin downstream UI/feature behavior.
"""

from __future__ import annotations

from src.infrastructure.ai.ai_provider_base import SYSTEM_PROMPT
from src.shared.constants.ai_explain_conclusion import EXPLAIN_MAX_LINES


def test_prompt_references_cp_stop_loss_as_invalidation() -> None:
    assert "CP stop-loss" in SYSTEM_PROMPT
    assert "invalidation" in SYSTEM_PROMPT.lower()


def test_prompt_references_cp_target_alongside_conclusion() -> None:
    assert "CP target" in SYSTEM_PROMPT


def test_prompt_restates_position_sizing_worked_example() -> None:
    assert "Position sizing" in SYSTEM_PROMPT
    assert "worked $ example" in SYSTEM_PROMPT


def test_prompt_covers_signal_triggers_confirm_or_contradict() -> None:
    assert "Signal triggers" in SYSTEM_PROMPT
    assert "CONFIRMS" in SYSTEM_PROMPT
    assert "CONTRADICTS" in SYSTEM_PROMPT


def test_prompt_uses_shared_max_lines_constant() -> None:
    """The MAX LINES marker must match ``EXPLAIN_MAX_LINES`` to avoid drift."""
    assert f"MAXIMUM {EXPLAIN_MAX_LINES} LINES" in SYSTEM_PROMPT


def test_prompt_forbids_invented_capital_figures() -> None:
    """Pinning the forbidden list catches accidental rule removals."""
    assert "Inventing capital figures" in SYSTEM_PROMPT


def test_prompt_explicitly_blocks_imperative_advice() -> None:
    """The trader-narrative rule must remain descriptive, never imperative."""
    assert "never imperative" in SYSTEM_PROMPT
