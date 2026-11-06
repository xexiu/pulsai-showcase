"""
Structured verdict the AI signal-explain emits as its final line.

Lives in the domain layer so the infrastructure parser AND the API schema
layer can both depend on it without crossing layer boundaries. Mirrors the
signal-action vocabulary so FE can color-code with existing styles.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.domain.enums import SignalAction
from src.shared.constants.ai_explain_conclusion import (
    EXPLAIN_CONCLUSION_CONFIDENCE_MAX,
    EXPLAIN_CONCLUSION_CONFIDENCE_MIN,
)

#: The AI explanation's verdict IS a trade action -- same members, same string values -- so it is that enum.
#: Until 2026-10-02 a mirrored StrEnum (concept_definitions); the wire values are unchanged.
ConclusionAction = SignalAction


class ExplainConclusion(BaseModel):
    """Parsed from the LLM's final Conclusion line.

    `null` in the parent response when parsing failed; FE then falls back
    to showing only the explanation text.

    When the LLM emits the multi-target form (``targets $A / $B / $C``),
    ``targets`` holds the full ordered list (nearest → farthest), and
    ``target_price`` mirrors the first entry for backwards-compatible
    consumers that only read the primary target.
    """

    action: ConclusionAction
    confidence_pct: int = Field(
        ge=EXPLAIN_CONCLUSION_CONFIDENCE_MIN,
        le=EXPLAIN_CONCLUSION_CONFIDENCE_MAX,
        description="AI's reported confidence in the action, 0..100.",
    )
    target_price: float = Field(
        gt=0,
        description="Primary (nearest) technical price level cited by the model.",
    )
    targets: list[float] | None = Field(
        default=None,
        description=(
            "Full ordered list of cited target prices (nearest → farthest) when"
            " the model emits the multi-target Conclusion form. ``None`` for"
            " single-target Conclusions."
        ),
    )
