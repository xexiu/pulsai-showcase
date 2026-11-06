"""
Reference-backed chart pattern metrics shared across AI and API layers.

Keep the raw dataset and generic prompt/response formatting here so both
application services and AI providers depend on a cross-layer shared module,
not on infrastructure packaging.
"""

from __future__ import annotations

from dataclasses import dataclass


def _expected_side_from_avg_move_label(avg_move_label: str) -> int:
    """Bulkowski avg-move label → trade side: rise=+1 (long), decline=-1 (short)."""
    label = (avg_move_label or "").strip().lower()
    if "decline" in label:
        return -1
    if "rise" in label:
        return 1
    msg = f"cannot derive expected_side from avg_move_label={avg_move_label!r}"
    raise ValueError(msg)


@dataclass(frozen=True)
class PatternReferenceStat:
    """Public/source-backed pattern metric with scope caveats.

    ``expected_side``: +1 = Bulkowski bias is rise (long), -1 = decline (short).
    Always derived from ``avg_move_label`` so polarity cannot drift from the cited metric.
    """

    name: str
    metric_name: str
    metric_value: str
    avg_move_label: str
    avg_move_value: str
    scope_note: str
    source_name: str
    source_url: str
    expected_side: int  # +1 long / -1 short


def _stat(
    *,
    name: str,
    metric_name: str,
    metric_value: str,
    avg_move_label: str,
    avg_move_value: str,
    scope_note: str,
    source_name: str,
    source_url: str,
) -> PatternReferenceStat:
    return PatternReferenceStat(
        name=name,
        metric_name=metric_name,
        metric_value=metric_value,
        avg_move_label=avg_move_label,
        avg_move_value=avg_move_value,
        scope_note=scope_note,
        source_name=source_name,
        source_url=source_url,
        expected_side=_expected_side_from_avg_move_label(avg_move_label),
    )


PRIMARY_PATTERN_REFERENCE_STATS: tuple[PatternReferenceStat, ...] = (
    _stat(
        name="Triple Bottom",
        metric_name="percentage meeting price target",
        metric_value="74%",
        avg_move_label="average rise",
        avg_move_value="46%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Triple Bottoms",
        source_url="https://www.thepatternsite.com/tb.html",
    ),
    _stat(
        name="Double Bottom (Eve & Adam subtype reference)",
        metric_name="percentage meeting price target",
        metric_value="72%",
        avg_move_label="average rise",
        avg_move_value="42%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Eve & Adam Double Bottoms",
        source_url="https://www.thepatternsite.com/eadb.html",
    ),
    _stat(
        name="Inverse Head & Shoulders",
        metric_name="percentage meeting price target",
        metric_value="71%",
        avg_move_label="average rise",
        avg_move_value="45%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Head-and-Shoulders Bottom",
        source_url="https://www.thepatternsite.com/hsb.html",
    ),
    _stat(
        name="Ascending Triangle (upward breakout)",
        metric_name="percentage meeting price target",
        metric_value="70%",
        avg_move_label="average rise",
        avg_move_value="43%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Ascending Triangle",
        source_url="https://thepatternsite.com/at.html",
    ),
)

SECONDARY_PATTERN_REFERENCE_STATS: tuple[PatternReferenceStat, ...] = (
    _stat(
        name="Double Top (Adam & Adam subtype reference)",
        metric_name="percentage meeting price target",
        metric_value="64%",
        avg_move_label="average decline",
        avg_move_value="15%",
        scope_note="subtype-specific public page summary",
        source_name="ThePatternSite / Bulkowski Adam & Adam Double Tops",
        source_url="https://www.thepatternsite.com/aadt.html",
    ),
    _stat(
        name="Falling Wedge (upward breakout)",
        metric_name="percentage meeting price target",
        metric_value="62%",
        avg_move_label="average rise",
        avg_move_value="38%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Falling Wedge",
        source_url="https://www.thepatternsite.com/fallwedge.html",
    ),
    _stat(
        name="Head & Shoulders Top",
        metric_name="percentage meeting price target",
        metric_value="51%",
        avg_move_label="average decline",
        avg_move_value="16%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Head-and-Shoulders Top",
        source_url="https://www.thepatternsite.com/hst.html",
    ),
    _stat(
        name="Pipe Bottom (upward breakout)",
        metric_name="percentage meeting price target",
        metric_value="77%",
        avg_move_label="average rise",
        avg_move_value="54%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Pipe Bottoms",
        source_url="https://thepatternsite.com/pipeb.html",
    ),
    _stat(
        name="Rectangle Bottom (upward breakout)",
        metric_name="percentage meeting price target",
        metric_value="79%",
        avg_move_label="average rise",
        avg_move_value="48%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Rectangle Bottoms",
        source_url="https://thepatternsite.com/rectbots.html",
    ),
    _stat(
        name="High and Tight Flag (upward breakout)",
        metric_name="percentage meeting price target",
        metric_value="82%",
        avg_move_label="average rise",
        avg_move_value="39%",
        scope_note="bull market results, his own half-height target",
        source_name="ThePatternSite / Bulkowski High and Tight Flags",
        source_url="https://thepatternsite.com/htf.html",
    ),
    _stat(
        name="Descending Triangle (downward breakout)",
        metric_name="percentage meeting price target",
        metric_value="50%",
        avg_move_label="average decline",
        avg_move_value="15%",
        scope_note="bull market results",
        source_name="ThePatternSite / Bulkowski Descending Triangle",
        source_url="https://www.thepatternsite.com/dt.html",
    ),
)

ALL_PATTERN_REFERENCE_STATS: tuple[PatternReferenceStat, ...] = PRIMARY_PATTERN_REFERENCE_STATS + SECONDARY_PATTERN_REFERENCE_STATS

DEPRIORITIZED_PATTERN_REFERENCES: tuple[str, ...] = (
    "Symmetric Triangle",
    "Rectangle",
    "Cup & Handle",
    "Flag/Pennant",
    "Rising Wedge in uptrend",
)


def _format_pattern_reference_line(stat: PatternReferenceStat) -> str:
    return f"- {stat.name}: {stat.metric_name} {stat.metric_value}; {stat.avg_move_label} {stat.avg_move_value} ({stat.scope_note})"


def build_chart_analysis_reference_system_prompt() -> str:
    """Build the shared prompt contract for vision-capable AI providers."""
    primary_lines = "\n".join(_format_pattern_reference_line(stat) for stat in PRIMARY_PATTERN_REFERENCE_STATS)
    secondary_lines = "\n".join(_format_pattern_reference_line(stat) for stat in SECONDARY_PATTERN_REFERENCE_STATS)
    ignored_lines = "\n".join(f"- {name}" for name in DEPRIORITIZED_PATTERN_REFERENCES)

    return f"""You are an expert technical chart analyst using public Bulkowski-style chart pattern references as context.

If you mention any historical metric, use ONLY the exact metric names below. Do not rewrite them as generic "success rate".

PRIMARY reference-backed chart patterns:
{primary_lines}

SECONDARY reference-backed chart patterns (use lower confidence than the primary group):
{secondary_lines}

DIVERGENCES:
- RSI and MACD divergences can be used as confirmation signals.
- Do not attach a hard historical percentage to divergences unless the source and metric name are explicit.

DE-PRIORITIZE these patterns unless the chart evidence is unusually strong:
{ignored_lines}

When you discuss a pattern:
1. Name the pattern clearly.
2. If you cite historical performance, name the metric exactly (for example "percentage meeting price target").
3. Keep scope caveats when relevant (subtype, breakout direction, bull market results).
4. Treat the reference metrics as context, not deterministic probabilities.

RESPONSE FORMAT:
1. List detected patterns with confidence level.
2. Note any divergences between price and indicators.
3. Identify key support/resistance levels visible on chart.
4. Provide a brief analysis summary.

DO NOT:
- Give trading recommendations or advice.
- Claim unsupported percentages.
- Use vague phrases like "93% success rate".
- Make price predictions."""


def build_mock_chart_analysis_response() -> str:
    """Mock response aligned with the reference-backed metric contract."""
    return """**Chart Analysis (Mock Mode - Reference Metrics)**

**Reference-backed patterns detected:**

1. **Double Bottom**
   - Reference metric: percentage meeting price target 72%
   - Scope: Eve & Adam subtype reference, bull market results
   - Average rise: 42%
   - Two distinct lows at a similar price level
   - Confirmation line visible at a recent swing high

2. **Bullish RSI Divergence**
   - Used as confirmation only
   - No hard historical percentage attached in this mock response
   - Price is making lower lows while RSI is making higher lows

**Support/Resistance Levels:**
- Support: Recent swing lows
- Resistance: Previous consolidation zone

**Summary:**
The chart shows a possible bullish reversal setup with a double bottom structure and
supporting RSI divergence. Historical metrics, when cited, use named reference measures
instead of generic success-rate wording.

---
*Mock mode - Enable a vision provider for live chart analysis.*"""
