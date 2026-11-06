"""
Structured sections for AI signal-explain RAG context.

Extracted from rag_context.py to respect module line limits (CODING_STANDARDS).

Each formatter is registered with the section registry at module load,
so the admin UI (Phase 4) auto-discovers them and the prompt builder
iterates the registry instead of a hardcoded if/append chain.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from src.domain.enums import SignalAction, SubscriptionTier
from src.infrastructure.ai.rag_explain_indicator_blocks import (
    format_indicators_split_block,
    format_loose_value,
    format_model_metrics_block,
    format_recent_candles_block,
    humanize_snake,
)
from src.infrastructure.ai.rag_explain_news_blocks import (
    format_external_news_block,
    format_news_sentiment_block,
    format_onchain_block,
)
from src.infrastructure.ai.rag_explain_technical_levels import format_technical_levels_block
from src.infrastructure.ai.rag_section_registry import (
    ContextSection,
    SectionInputs,
    register_section,
)

if TYPE_CHECKING:
    from src.domain.services.confluence_explain_summary import ConfluenceExplainSummary
from src.shared.constants.ai_explain_conclusion import (
    KELLY_EXAMPLE_CAPITAL_USD,
    SIGNAL_TRIGGER_FEATURE_KEYS,
)

TOP_FEATURE_IMPORTANCE_LINES = 15


def format_explain_signal_header(
    signal: dict[str, Any],
    *,
    signal_type: str | None,
    meta_score: float | None,
) -> str:
    lines = ["## Signal Data (ML headline)"]

    symbol = signal.get("symbol", "Unknown")
    action = signal.get("action", "Unknown")
    confidence = signal.get("confidence", 0)
    timeframe = signal.get("timeframe", "1h")
    model_version = signal.get("model_version", "Unknown")

    lines.append(f"- Symbol: {symbol}")
    lines.append(f"- Action: {action}")
    if isinstance(confidence, (int, float)):
        lines.append(f"- Confidence: {float(confidence):.0%}")
    else:
        lines.append(f"- Confidence: {format_loose_value(confidence)}")
    lines.append(f"- Timeframe: {timeframe}")
    lines.append(f"- Model: {model_version}")

    price = signal.get("price")
    if isinstance(price, (int, float)):
        lines.append(f"- Price at signal time: ${float(price):,.2f}")

    if signal_type:
        lines.append(f"- Signal source type: {signal_type}")

    if meta_score is not None:
        lines.append(f"- Meta-Agent ensemble score: {float(meta_score):+.3f} (scale: -1.0 = max SELL bias, 0 = neutral, +1.0 = max BUY bias)")

    if "created_at" in signal and signal["created_at"] is not None:
        lines.append(f"- Generated: {signal['created_at']}")

    return "\n".join(lines)


def format_weighted_consensus_block(model_votes: list[Any] | None) -> str | None:
    if not model_votes:
        return None
    lines: list[str] = ["## Weighted consensus (per-component votes)"]

    def _vote_sort_key(v: object) -> str:
        if isinstance(v, dict):
            return str(v.get("model_type", ""))
        return ""

    for vote in sorted(model_votes, key=_vote_sort_key):
        if not isinstance(vote, dict):
            continue
        row: dict[str, Any] = vote
        mtype = row.get("model_type", "unknown")
        action = row.get("action", "?")
        conf = row.get("confidence")
        weight = row.get("weight", 1.0)
        ver = row.get("model_version", "")
        conf_s = f"{float(conf):.1%}" if isinstance(conf, (int, float)) else str(conf)
        weight_s = f"{float(weight):.1%}" if isinstance(weight, (int, float)) else str(weight)
        lines.append(f"- Component `{mtype}` (model_version={ver}): action={action}, confidence={conf_s}, weight={weight_s}")
    return "\n".join(lines)


def format_classic_sources_block(classic_sources: dict[str, bool] | None) -> str | None:
    if not classic_sources:
        return None
    fired = sorted(k for k, v in classic_sources.items() if v)
    if not fired:
        return None
    lines = ["## Classic / rule-based TA (detectors that fired)"]
    lines.extend(f"- {humanize_snake(key)} (`{key}`)" for key in fired)
    return "\n".join(lines)


def format_feature_importance_block(feature_importance: dict[str, Any] | None) -> str | None:
    if not feature_importance:
        return None
    scored: list[tuple[str, float]] = []
    for name, raw in feature_importance.items():
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            scored.append((str(name), float(raw)))
    if not scored:
        return None
    scored.sort(key=lambda t: abs(t[1]), reverse=True)
    top = scored[:TOP_FEATURE_IMPORTANCE_LINES]
    lines = ["## ML feature influence (top contributors; informational)"]
    for name, val in top:
        lines.append(f"- {humanize_snake(name)} (`{name}`): {format_loose_value(val)}")
    return "\n".join(lines)


def format_position_sizing_block(suggested_position_pct: float | None) -> str | None:
    """Render the Kelly sizing block with a CONCRETE capital example.

    Previously rendered just the percentage, which left users (the screenshot
    showed "5.0% Tamaño Kelly" with no context) wondering what 5% means in
    dollars. Now appends a worked example using
    ``KELLY_EXAMPLE_CAPITAL_USD`` as the reference capital, e.g.::

        Suggested fraction of capital: 5.00% (illustrative Kelly-style hint)
        Worked example: 5.00% of a $1,000 reference capital = $50.00 position.

    The example capital is display-only — does NOT touch any real sizing
    pipeline. Real position sizing is the ``suggested_position_pct`` fraction
    applied to the user's actual balance by the live trading path.
    """
    if suggested_position_pct is None:
        return None
    pct = float(suggested_position_pct)
    example_capital = KELLY_EXAMPLE_CAPITAL_USD
    example_position = pct * example_capital
    lines = [
        "## Position sizing (illustrative Kelly-style hint)",
        f"- Suggested fraction of capital (confidence-only half-Kelly proxy): {pct:.2%}",
        f"- Worked example: {pct:.2%} of a ${example_capital:,.0f} reference capital = ${example_position:,.2f} position.",
        "- Not personal advice; not based on your account or trade history.",
    ]
    return "\n".join(lines)


# Friendly labels for the binary signal-trigger keys exposed by the feature
# pipeline. Defined ABOVE the consumer for top-down readability; values map
# directly to the keys in ``SIGNAL_TRIGGER_FEATURE_KEYS``.
_SIGNAL_TRIGGER_LABELS: dict[str, str] = {
    "signal_stochastic_crossover": "Stochastic crossover (ST)",
    "rsi_divergence": "RSI divergence",
    "macd_divergence": "MACD divergence",
}


def format_signal_triggers_block(model_input_features: dict[str, Any] | None) -> str | None:
    """Render binary signal-trigger features (ST crossover, RSI/MACD divergences).

    The feature engine emits these as ``+1`` (bullish), ``-1`` (bearish), ``0``
    (neutral). Lines collapse to neutral/missing rows so the LLM sees them only
    when they're active. ``None`` when no listed trigger is present in the
    feature vector — keeps the block out of the prompt when there's nothing
    to say.

    Why a dedicated section: these are NOT price levels (so they don't fit
    ``technical_levels``) and NOT raw indicator values (so they don't fit
    ``indicators``). They're discrete "this rule fired now" signals — closer
    to ``classic_sources`` semantically — and benefit from their own section
    label so the LLM can call them out explicitly.
    """
    features = model_input_features or {}
    rows: list[str] = []
    for key in SIGNAL_TRIGGER_FEATURE_KEYS:
        raw = features.get(key)
        if not isinstance(raw, (int, float, bool)):
            continue
        value = float(raw)
        if not math.isfinite(value) or value == 0.0:
            continue
        label = _SIGNAL_TRIGGER_LABELS.get(key, humanize_snake(key))
        direction = "bullish" if value > 0 else "bearish"
        rows.append(f"- {label}: {direction} ({key} = {value:+.0f})")
    if not rows:
        return None
    return "\n".join(["## Signal triggers (active rule detections)", *rows])


def format_confluence_header_block(summary: ConfluenceExplainSummary) -> str:
    """Combined multi-timeframe confluence header for the explainer prompt.

    Frames the LLM that this is ONE decision spanning several timeframes: lists each
    leg, the dominant direction + how many timeframes back it, and explicitly flags a
    BUY-vs-SELL conflict so the explanation warns instead of averaging it away.
    """
    legs_str = ", ".join(f"{leg.timeframe}={leg.action}({leg.confidence:.0%})" for leg in summary.legs)
    lines = [
        f"## Multi-Timeframe Confluence: {summary.symbol}",
        f"- Timeframes ({summary.total}): {legs_str}",
    ]
    if summary.dominant_action == "MIXED":
        lines.append("- Dominant: MIXED (no directional majority across timeframes)")
    else:
        lines.append(
            f"- Dominant: {summary.dominant_action} "
            f"({summary.agreeing_count} of {summary.total} timeframe(s) agree, mean confidence {summary.mean_confidence:.0%})"
        )
    lines.append(f"- Unanimous across timeframes: {'yes' if summary.is_unanimous else 'no'}")
    if summary.is_conflicted:
        lines.append("- CONFLICT: timeframes disagree (BUY vs SELL) - weight this cautiously.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section registry — declares each block as a discoverable, configurable unit.
# Order here = order in the final prompt. Default-enabled preserves the
# pre-registry behavior (every block was unconditionally appended when data
# was present).
# ---------------------------------------------------------------------------


def _build_signal_header(inputs: SectionInputs) -> str | None:
    return format_explain_signal_header(
        inputs.signal,
        signal_type=inputs.signal_type,
        meta_score=inputs.meta_score,
    )


def _build_weighted_consensus(inputs: SectionInputs) -> str | None:
    return format_weighted_consensus_block(inputs.model_votes)


def _build_classic_sources(inputs: SectionInputs) -> str | None:
    return format_classic_sources_block(inputs.classic_sources)


def _build_feature_importance(inputs: SectionInputs) -> str | None:
    return format_feature_importance_block(inputs.feature_importance)


def _build_position_sizing(inputs: SectionInputs) -> str | None:
    return format_position_sizing_block(inputs.suggested_position_pct)


def _build_technical_levels(inputs: SectionInputs) -> str | None:
    price_raw = inputs.signal.get("price")
    price = float(price_raw) if isinstance(price_raw, (int, float)) else None
    action_raw = inputs.signal.get("action")
    action = action_raw.value if isinstance(action_raw, SignalAction) else action_raw
    return format_technical_levels_block(price, inputs.model_input_features, action)


def _build_signal_triggers(inputs: SectionInputs) -> str | None:
    return format_signal_triggers_block(inputs.model_input_features)


def _build_indicators_split(inputs: SectionInputs) -> str | None:
    if not inputs.indicators:
        return None
    text = format_indicators_split_block(inputs.indicators)
    return text or None


def _build_model_metrics(inputs: SectionInputs) -> str | None:
    return format_model_metrics_block(inputs.model_metrics)


def _build_recent_candles(inputs: SectionInputs) -> str | None:
    return format_recent_candles_block(inputs.recent_candles)


def _build_external_news(inputs: SectionInputs) -> str | None:
    return format_external_news_block(inputs.external_news, cite_sources=inputs.cite_sources)


def _build_news_sentiment(inputs: SectionInputs) -> str | None:
    return format_news_sentiment_block(inputs.news_sentiment)


def _build_onchain(inputs: SectionInputs) -> str | None:
    return format_onchain_block(inputs.onchain)


_SECTIONS_REGISTERED = False


def _register_default_sections() -> None:
    global _SECTIONS_REGISTERED
    if _SECTIONS_REGISTERED:
        return
    _SECTIONS_REGISTERED = True

    register_section(
        ContextSection(
            key="signal_header",
            display_name="Signal header",
            description="Core signal facts (symbol, action, confidence, timeframe, meta-agent score).",
            build=_build_signal_header,
        )
    )
    register_section(
        ContextSection(
            key="weighted_consensus",
            display_name="ML weighted consensus",
            description="Per-component model votes with weights and confidences.",
            build=_build_weighted_consensus,
        )
    )
    register_section(
        ContextSection(
            key="classic_sources",
            display_name="Classic TA rules fired",
            description="Rule-based detectors that triggered (RSI, MACD crossover, etc.).",
            build=_build_classic_sources,
        )
    )
    register_section(
        ContextSection(
            key="feature_importance",
            display_name="ML feature importance",
            description="Top-N feature contributions from the ML model.",
            build=_build_feature_importance,
        )
    )
    register_section(
        ContextSection(
            key="position_sizing",
            display_name="Position sizing hint",
            description="Confidence-only half-Kelly proxy. Illustrative, not personal advice.",
            build=_build_position_sizing,
        )
    )
    register_section(
        ContextSection(
            key="technical_levels",
            display_name="Technical levels (target anchors)",
            description=(
                "Snapshot price + nearest support/resistance levels (from dist_to_support_N / "
                "dist_to_resistance_N features). Anchors BUY/SELL Conclusion targets to real "
                "levels instead of the entry price."
            ),
            build=_build_technical_levels,
        )
    )
    register_section(
        ContextSection(
            key="signal_triggers",
            display_name="Signal triggers",
            description=(
                "Active rule detectors emitted by the feature pipeline: Stochastic crossover (ST),"
                " RSI divergence, MACD divergence. Encoded as bullish (+1) / bearish (-1) signals;"
                " only firing detectors appear so the LLM can cite confirmation evidence."
            ),
            build=_build_signal_triggers,
        )
    )
    register_section(
        ContextSection(
            key="indicators",
            display_name="Technical indicators",
            description="Canonical TA (RSI, MACD, Bollinger, price) plus supplementary numeric inputs.",
            build=_build_indicators_split,
        )
    )
    register_section(
        ContextSection(
            key="model_metrics",
            display_name="Model performance metrics",
            description="Backtest stats: accuracy, Sharpe, win rate, recent signal count.",
            build=_build_model_metrics,
        )
    )
    register_section(
        ContextSection(
            key="recent_candles",
            display_name="Recent price action",
            description="Period high/low/change summary from recent candles.",
            build=_build_recent_candles,
        )
    )
    register_section(
        ContextSection(
            key="external_news",
            display_name="Market news",
            description="Curated external news headlines relevant to the symbol.",
            build=_build_external_news,
        )
    )
    register_section(
        ContextSection(
            key="news_sentiment",
            display_name="News sentiment (aggregate)",
            description="Normalized headline-sentiment score with label and source count.",
            build=_build_news_sentiment,
        )
    )
    register_section(
        ContextSection(
            key="onchain",
            display_name="On-chain metrics",
            description="MVRV / SOPR / exchange-flow snapshot. BTC-only; PRO tier and above.",
            build=_build_onchain,
            requires_tier=SubscriptionTier.PRO,
        )
    )


_register_default_sections()
