"""
Parser + trimmer for the AI signal-explain Conclusion line.

Single responsibility: take raw LLM text → (trimmed explanation, parsed
conclusion or None). Separated from the response Pydantic schemas (data
contract) and from the AI provider call (transport) so each layer is unit-
testable without the others.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from src.domain.models.explain_conclusion import ConclusionAction, ExplainConclusion
from src.shared.constants.ai_explain_conclusion import (
    EXPLAIN_CONCLUSION_LINE_PREFIX,
    EXPLAIN_CONCLUSION_MULTI_REGEX,
    EXPLAIN_CONCLUSION_REGEX,
    EXPLAIN_MAX_LINES,
)

logger = logging.getLogger(__name__)

# Minimum number of price tokens a multi-target Conclusion line must carry —
# fewer than this collapses to "not a valid multi-target form" so the parser
# bails instead of returning a single-element list (the single-target form
# uses a different keyword + regex anyway).
_MULTI_TARGET_MIN_PRICES: int = 2


def parse_conclusion_from_explanation(text: str) -> ExplainConclusion | None:
    """Find and parse the final `Conclusion:` line; return None on any failure.

    Scans from the bottom up — the last matching line wins. Tolerates trailing
    whitespace, blank lines after the conclusion (some providers append empty
    newlines), and a missing trailing "est" qualifier.

    Supports BOTH forms (multi-target tried first; falls back to single):
    - ``Conclusion: BUY 80% target $1000 est``
    - ``Conclusion: BUY 80% targets $1000 / $1050 / $1100 est``
    """
    if not text:
        return None

    for raw_line in reversed(text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        if EXPLAIN_CONCLUSION_LINE_PREFIX.lower() not in line.lower():
            # Non-conclusion lines BELOW the conclusion are tolerated — the
            # provider appends a localized disclaimer block via
            # ``_format_response`` after the body. Keep walking up until we
            # either find a Conclusion line or exhaust the text.
            continue
        # Try multi first (more specific grammar), then single. If NEITHER
        # parses, this line is prose like ``- Conclusion: see appendix`` —
        # keep walking up so a canonical earlier line still wins.
        parsed = _parse_multi_target(line) or _parse_single_target(line)
        if parsed is not None:
            return parsed
        # Loop again; the prose match wasn't the real Conclusion line.

    return None


def _parse_single_target(line: str) -> ExplainConclusion | None:
    """Parse the legacy single-target Conclusion form. ``None`` on any failure."""
    match = EXPLAIN_CONCLUSION_REGEX.match(line)
    if match is None:
        logger.info("Conclusion line found but failed to parse: %r", line)
        return None
    try:
        action = ConclusionAction(match.group("action").upper())
        confidence = int(match.group("confidence"))
        target_price = float(match.group("price").replace(",", ""))
    except (ValueError, KeyError) as exc:
        logger.info("Conclusion parse error: %s for line %r", exc, line)
        return None
    if target_price <= 0:
        return None
    try:
        return ExplainConclusion(
            action=action,
            confidence_pct=confidence,
            target_price=target_price,
        )
    except ValidationError as exc:
        # Out-of-bounds confidence (>100) or non-positive price land here.
        logger.info("Conclusion failed schema validation: %s for line %r", exc, line)
        return None


def _parse_multi_target(line: str) -> ExplainConclusion | None:
    """Parse the multi-target form ``targets $A / $B / $C``. ``None`` if not the multi form."""
    match = EXPLAIN_CONCLUSION_MULTI_REGEX.match(line)
    if match is None:
        return None
    try:
        action = ConclusionAction(match.group("action").upper())
        confidence = int(match.group("confidence"))
    except (ValueError, KeyError) as exc:
        logger.info("Multi-target Conclusion parse error: %s for line %r", exc, line)
        return None
    raw_prices = match.group("prices")
    # The outer regex already validated each price slot's shape (digits + optional
    # ,/. + optional leading $). Split + strip + float() is enough here — no need
    # for a second regex per token (drops a duplicate SoT for the price grammar).
    tokens: list[float] = []
    for chunk in raw_prices.split("/"):
        cleaned = chunk.strip().lstrip("$").replace(",", "")
        try:
            value = float(cleaned)
        except ValueError as exc:
            # Shouldn't happen — outer regex prevents it — but degrade safely.
            logger.info("Multi-target price value error: %s for token %r in %r", exc, chunk, line)
            return None
        if value <= 0:
            return None
        tokens.append(value)
    if len(tokens) < _MULTI_TARGET_MIN_PRICES:
        return None
    try:
        return ExplainConclusion(
            action=action,
            confidence_pct=confidence,
            target_price=tokens[0],
            targets=tokens,
        )
    except ValidationError as exc:
        logger.info("Multi-target Conclusion failed schema validation: %s for line %r", exc, line)
        return None


def trim_explanation_to_max_lines(text: str, *, max_lines: int = EXPLAIN_MAX_LINES) -> str:
    """Clamp the explanation to `max_lines` non-empty lines, preserving the Conclusion.

    Strategy: keep the first (max_lines - 1) non-empty lines as the body, then
    re-append the Conclusion line if one exists in the original text. If no
    conclusion is present, simply truncate to `max_lines` non-empty lines.
    """
    if not text:
        return text

    lines = text.splitlines()
    non_empty = [ln for ln in lines if ln.strip()]
    if len(non_empty) <= max_lines:
        return text

    conclusion_line: str | None = None
    for ln in reversed(non_empty):
        if EXPLAIN_CONCLUSION_LINE_PREFIX.lower() in ln.lower():
            conclusion_line = ln
            break

    if conclusion_line is None:
        return "\n".join(non_empty[:max_lines])

    body_budget = max_lines - 1
    body_lines = [ln for ln in non_empty if ln is not conclusion_line][:body_budget]
    return "\n".join([*body_lines, conclusion_line])
