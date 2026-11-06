"""
Single source of truth for the AI signal-explain Conclusion line.

The model is instructed to terminate its explanation with one line in this
exact format. The parser uses the regex below; the prompt template references
the same prefix + structure. Keeping both in one module means a future format
change touches one file.
"""

from __future__ import annotations

import re
from typing import Final

# Hard cap on explanation lines (post-trim). LLM is also told this in the prompt.
EXPLAIN_MAX_LINES: Final[int] = 150

# Reference capital used to render the Kelly sizing section's concrete example
# (e.g. "5% of $1,000 capital = $50 position"). Display-only — does NOT affect
# any real position sizing; the real Kelly fraction is the user's
# ``suggested_position_pct`` independent of this reference number.
KELLY_EXAMPLE_CAPITAL_USD: Final[float] = 1_000.0

# When the chosen action is NOT one of BUY/SELL/HOLD but the weighted consensus
# still shows >= this percentage for an alternative action, the explanation
# must call it out (e.g. "Note: 16.1% SELL component present even though
# headline action is HOLD"). Picked at 10% as the threshold where a dissenting
# signal becomes noteworthy without flagging every minor noise vote.
DISSENT_MENTION_THRESHOLD_PCT: Final[float] = 10.0

# Curated feature-vector keys that carry directional "where could the price
# go next" information. Used by the technical-levels RAG section to compute
# action-anchored target prices without dragging the entire feature dict
# into the prompt context.
TECHNICAL_LEVEL_FEATURE_KEYS: Final[tuple[str, ...]] = (
    "dist_to_support_5",
    "dist_to_resistance_5",
    "dist_to_support_20",
    "dist_to_resistance_20",
    "atr_7",
    "atr_14",
    "bb_width",
    # Keltner upper/lower (absolute prices, ATR-anchored EMA bands). Wider /
    # more breakout-friendly than BB std-dev bands in trending regimes; give
    # the LLM and the action-target SoT an alternative resistance/support
    # level the dist_to_* % features can't express directly.
    "keltner_upper",
    "keltner_lower",
    # Chart-pattern (CP) zones from double-bottom / double-top detection
    # (``domain/services/features/feature_chart_pattern.py``). NOT the same
    # as ``dist_to_*_20`` — those are proximity-to-pivot percentages, while
    # CP levels are geometric entry/target prices derived from confirmed
    # pattern legs. Including both gives the LLM two independent views of
    # support / resistance.
    "cp_resistance_line",
    "cp_support_line",
    "cp_target",
    "cp_stop_loss",
)

# Binary or score signal-triggers the model sees per bar. Surfaced in a
# dedicated "Signal triggers" RAG section so the LLM can reference active
# detectors without us encoding their semantics in the prompt template.
# Values are +1 / 0 / -1 (bullish / neutral / bearish) by convention.
SIGNAL_TRIGGER_FEATURE_KEYS: Final[tuple[str, ...]] = (
    "signal_stochastic_crossover",
    "rsi_divergence",
    "macd_divergence",
)

# Confidence is an integer percentage 0..100.
EXPLAIN_CONCLUSION_CONFIDENCE_MIN: Final[int] = 0
EXPLAIN_CONCLUSION_CONFIDENCE_MAX: Final[int] = 100

# The conclusion line MUST start with this exact prefix.
EXPLAIN_CONCLUSION_LINE_PREFIX: Final[str] = "Conclusion:"

# Format the model is instructed to emit on the final line.
# Used both as the example shown to the LLM and as the human-readable contract.
EXPLAIN_CONCLUSION_LINE_FORMAT: Final[str] = "Conclusion: <BUY|SELL|HOLD> <CONFIDENCE>% target $<PRICE> est"

# Strict parser. Case-insensitive on the action so we tolerate LLM quirks.
# The trailing "est" qualifier is optional in parsing (LLMs sometimes drop it)
# but emitted by the template to make the estimate framing explicit.
EXPLAIN_CONCLUSION_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^Conclusion:\s*"
    r"(?P<action>BUY|SELL|HOLD)\s+"
    r"(?P<confidence>\d{1,3})%\s+"
    r"target\s+\$?(?P<price>[0-9][0-9,]*(?:\.[0-9]+)?)"
    r"(?:\s+est\.?)?\s*$",
    re.IGNORECASE,
)

# Multi-target form: ``targets $A / $B / $C`` (2..4 prices). Captures the entire
# ``$A / $B / $C`` substring as ``prices`` so the parser can split / re-validate
# each token individually. The slash separator is the convention; surrounding
# whitespace is flexible. Note the ``targets`` (plural) keyword distinguishes
# from the single-target form. Empty entries are disallowed by the inner regex.
EXPLAIN_CONCLUSION_MULTI_REGEX: Final[re.Pattern[str]] = re.compile(
    r"^Conclusion:\s*"
    r"(?P<action>BUY|SELL)\s+"
    r"(?P<confidence>\d{1,3})%\s+"
    r"targets\s+"
    r"(?P<prices>\$?[0-9][0-9,]*(?:\.[0-9]+)?"
    r"(?:\s*/\s*\$?[0-9][0-9,]*(?:\.[0-9]+)?){1,3})"
    r"(?:\s+est\.?)?\s*$",
    re.IGNORECASE,
)
