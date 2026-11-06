"""
RAG Context Builder (Sprint 1.7)

Builds context for AI prompts using Retrieval Augmented Generation (RAG).

ARCHITECTURE:
- Collects data from internal sources (signals, indicators, etc.)
- Adds curated external context (news from ai-sources.yaml)
- Formats into structured prompt for Claude
- Respects token limits and guardrails

WHY RAG?
- Grounds AI responses in real data (reduces hallucinations)
- Provides up-to-date information (model knowledge cutoff)
- Makes responses verifiable (cites sources)
"""

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from src.domain.services.position_sizing.kelly import heuristic_suggested_position_fraction
from src.infrastructure.ai.rag_explain_indicator_blocks import format_indicators_split_block
from src.infrastructure.ai.rag_explain_news_blocks import (
    format_news_sentiment_block,
    format_onchain_block,
)
from src.infrastructure.ai.rag_explain_signal_sections import (
    format_confluence_header_block,
    format_explain_signal_header,
)
from src.infrastructure.ai.rag_section_registry import (
    SectionInputs,
    iter_effective_sections,
)
from src.infrastructure.ai.sources_loader import (
    get_ai_guardrails,
    get_context_template,
)

if TYPE_CHECKING:
    from src.domain.enums import SubscriptionTier
    from src.domain.services.confluence_explain_summary import ConfluenceExplainSummary

logger = logging.getLogger(__name__)


def build_explain_context_from_telegram_dict(
    signal_dict: dict[str, Any],
    *,
    news_sentiment: dict[str, Any] | None = None,
    onchain: dict[str, Any] | None = None,
    enabled_section_keys: set[str] | None = None,
    user_tier: SubscriptionTier | str | None = None,
    max_context_tokens: int | None = None,
) -> str:
    """Build the same RAG blob as HTTP `/ai/explain-signal` from a Telegram/API-shaped dict.

    Extra kwargs (Phase 4):
    - `news_sentiment` / `onchain` — payloads to feed the matching ContextSections.
    - `enabled_section_keys` — admin-controlled enabled set; `None` = registry defaults.
    - `user_tier` — for tier-gated sections.
    - `max_context_tokens` — override the truncation budget (admin snapshot value).
    """
    raw_confidence = signal_dict.get("confidence", 0.0)
    confidence = float(raw_confidence) if isinstance(raw_confidence, (int, float)) else 0.0

    classic_raw = signal_dict.get("classic_sources")
    classic_norm: dict[str, bool] | None = None
    if isinstance(classic_raw, dict) and classic_raw:
        classic_norm = {str(k): bool(v) for k, v in classic_raw.items()}

    fi = signal_dict.get("feature_importance")
    fi_out: dict[str, Any] | None = None
    if isinstance(fi, dict) and fi:
        fi_out = dict(fi)

    votes = signal_dict.get("model_votes")
    votes_out: list[dict[str, Any]] | None = votes if isinstance(votes, list) else None

    raw_meta = signal_dict.get("meta_score")
    meta_out: float | None = None
    if isinstance(raw_meta, (int, float)):
        meta_out = float(raw_meta)

    st_raw = signal_dict.get("signal_type")
    signal_type_str: str | None = str(st_raw) if st_raw is not None else None

    core_signal: dict[str, Any] = {
        "id": signal_dict.get("id"),
        "symbol": signal_dict.get("symbol", "Unknown"),
        "action": signal_dict.get("action", "Unknown"),
        "confidence": confidence,
        "timeframe": signal_dict.get("timeframe", "1h"),
        "model_version": signal_dict.get("model_version", "Unknown"),
        "created_at": signal_dict.get("created_at"),
        "price": signal_dict.get("price"),
    }

    ind = signal_dict.get("indicators")
    indicators_out: dict[str, Any] | None = ind if isinstance(ind, dict) and ind else None

    mif = signal_dict.get("model_input_features")
    features_out: dict[str, Any] | None = mif if isinstance(mif, dict) and mif else None

    builder = RAGContextBuilder(max_tokens=max_context_tokens)
    return builder.build_signal_context(
        SectionInputs(
            signal=core_signal,
            indicators=indicators_out,
            signal_type=signal_type_str,
            classic_sources=classic_norm,
            model_votes=votes_out,
            meta_score=meta_out,
            feature_importance=fi_out,
            suggested_position_pct=heuristic_suggested_position_fraction(confidence),
            news_sentiment=news_sentiment,
            onchain=onchain,
            model_input_features=features_out,
        ),
        enabled_section_keys=enabled_section_keys,
        user_tier=user_tier,
    )


def build_confluence_explain_context(
    summary: ConfluenceExplainSummary,
    signal_dicts: list[dict[str, Any]],
    *,
    news_sentiment: dict[str, Any] | None = None,
    onchain: dict[str, Any] | None = None,
    max_context_tokens: int | None = None,
) -> str:
    """Assemble ONE explainer context for a co-temporal multi-timeframe confluence.

    Confluence header (combined directional picture + conflict flag) + a condensed
    per-timeframe signal header for each leg + the shared news / on-chain sections
    ONCE (they are symbol/market-wide, not per-timeframe). A full per-timeframe RAG
    block would multiply the token budget; the header carries the cross-timeframe
    story instead. Reuses the single-signal formatters and the token-budget truncation.
    """
    return RAGContextBuilder(max_tokens=max_context_tokens).build_confluence_context(
        summary,
        signal_dicts,
        news_sentiment=news_sentiment,
        onchain=onchain,
    )


class RAGContextBuilder:
    """Builds RAG context for AI prompts (signals, chart analysis, news blocks).

    NOT the Builder pattern of ARCHITECTURE_PATTERNS.md section 1 -- the name is older than that table. It
    holds no fluent, partially-built state: each build_* call is a pure render of one immutable
    SectionInputs (the frozen dataclass that section names as the alternative to a Builder), truncated
    to the token budget this instance carries.
    """

    def __init__(self, max_tokens: int | None = None) -> None:
        """max_tokens defaults from ai-sources.yaml guardrails when omitted."""
        guardrails = get_ai_guardrails()
        self._max_tokens = max_tokens or guardrails.get("max_context_tokens", 8000)
        self._cite_sources = guardrails.get("cite_sources", True)

    def build_signal_context(
        self,
        inputs: SectionInputs,
        *,
        enabled_section_keys: set[str] | None = None,
        user_tier: SubscriptionTier | str | None = None,
    ) -> str:
        """Compose signal-explain RAG text by iterating the section registry.

        `enabled_section_keys=None` keeps the pre-registry behavior (every section
        with a non-empty build result is appended). When provided (Phase 4: admin
        config), only listed keys are emitted; `user_tier` further gates
        tier-restricted sections. ``inputs.cite_sources`` is overridden by this builder's guardrail.
        """
        inputs = replace(inputs, cite_sources=self._cite_sources)

        parts: list[str] = []

        template = get_context_template("signal_explanation")
        if template:
            parts.append(template.strip())

        for section in iter_effective_sections(
            enabled_keys=enabled_section_keys,
            user_tier=user_tier,
        ):
            block = section.build(inputs)
            if block:
                parts.append(block)

        context = "\n\n".join(parts)
        return self._truncate_to_token_limit(context)

    def build_confluence_context(
        self,
        summary: ConfluenceExplainSummary,
        signal_dicts: list[dict[str, Any]],
        *,
        news_sentiment: dict[str, Any] | None = None,
        onchain: dict[str, Any] | None = None,
    ) -> str:
        """Compose the multi-timeframe confluence explain context (see module function).

        Deliberately CONDENSED vs the single-signal builder: it renders the confluence
        header + one per-timeframe signal header, NOT the full per-timeframe section set
        (technical levels, feature importance, consensus, ...). Those x up to 6 timeframes
        would exceed the token budget and truncate; the confluence view is a directional
        overview, and a user can open a single timeframe for the deep dive. news/on-chain
        are passed pre-gated by the caller (tier-aware enabled_keys), so tier rules hold.
        """
        # First signal dict per timeframe (legs already ordered shortest→longest).
        by_tf: dict[str, dict[str, Any]] = {}
        for sig in signal_dicts:
            tf = sig.get("timeframe")
            if isinstance(tf, str) and tf not in by_tf:
                by_tf[tf] = sig

        parts: list[str] = []
        template = get_context_template("signal_explanation")
        if template:
            parts.append(template.strip())
        parts.append(format_confluence_header_block(summary))

        for leg in summary.legs:
            matched = by_tf.get(leg.timeframe)
            if matched is None:
                continue
            meta_raw = matched.get("meta_score")
            meta_score = float(meta_raw) if isinstance(meta_raw, (int, float)) else None
            st_raw = matched.get("signal_type")
            parts.append(
                format_explain_signal_header(
                    matched,
                    signal_type=str(st_raw) if st_raw is not None else None,
                    meta_score=meta_score,
                )
            )

        if news_sentiment:
            news_block = format_news_sentiment_block(news_sentiment)
            if news_block:
                parts.append(news_block)
        if onchain:
            onchain_block = format_onchain_block(onchain)
            if onchain_block:
                parts.append(onchain_block)

        return self._truncate_to_token_limit("\n\n".join(parts))

    def build_chart_context(
        self,
        symbol: str,
        timeframe: str,
        current_price: float,
        indicators: dict[str, Any] | None = None,
    ) -> str:
        """Chart vision/text context with optional indicator split (canonical + supplementary)."""
        parts: list[str] = []

        template = get_context_template("chart_analysis")
        if template:
            parts.append(template.strip())

        parts.append("## Chart Information")
        parts.append(f"- Symbol: {symbol}")
        parts.append(f"- Timeframe: {timeframe}")
        parts.append(f"- Current Price: ${current_price:,.2f}")

        if indicators:
            formatted_ind = format_indicators_split_block(indicators)
            if formatted_ind:
                parts.append(formatted_ind)

        context = "\n".join(parts)
        return self._truncate_to_token_limit(context)

    def _truncate_to_token_limit(self, context: str) -> str:
        """Rough limit: 1 token ≈ 4 characters."""
        max_chars = self._max_tokens * 4

        if len(context) <= max_chars:
            return context

        logger.warning(
            "Context truncated from %d to %d chars (token limit: %d)",
            len(context),
            max_chars,
            self._max_tokens,
        )

        return context[: max_chars - 50] + "\n\n[Context truncated due to length limit]"
