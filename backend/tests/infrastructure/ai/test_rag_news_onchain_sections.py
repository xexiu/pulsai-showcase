"""Unit tests for the news_sentiment and onchain RAG sections.

Behavior assertions:
- News-sentiment block is dropped when no texts were analyzed (placeholder).
- News-sentiment block surfaces normalized score, label, count, source.
- On-chain block is dropped for non-BTC pairs and provider=none.
- On-chain block surfaces MVRV/SOPR/exchange_flow rows + signal + stale note.
- Tier gating: onchain section is invisible to FREE/STARTER, visible to PRO/ELITE.
"""

from __future__ import annotations

from src.domain.enums import SubscriptionTier
from src.infrastructure.ai.rag_explain_news_blocks import (
    format_news_sentiment_block,
    format_onchain_block,
)
from src.infrastructure.ai.rag_section_registry import (
    get_section,
    iter_effective_sections,
)


class TestNewsSentimentBlock:
    def test_returns_none_when_snapshot_empty(self) -> None:
        assert format_news_sentiment_block(None) is None
        assert format_news_sentiment_block({}) is None

    def test_skipped_when_no_texts_analyzed(self) -> None:
        """Placeholder sentiment (n_texts=0) should NOT leak into the prompt."""
        snapshot = {
            "value": 0.0,
            "label": "neutral",
            "source": "headline_sentiment",
            "extras": {"n_texts": 0, "analysis_build": "pending"},
        }
        assert format_news_sentiment_block(snapshot) is None

    def test_emits_block_with_real_data(self) -> None:
        snapshot = {
            "value": -0.42,
            "raw_value": -0.42,
            "label": "fear",
            "source": "headline_sentiment",
            "extras": {"n_texts": 17, "analysis_build": "v1"},
        }
        block = format_news_sentiment_block(snapshot)
        assert block is not None
        assert "## News sentiment (aggregate)" in block
        assert "-0.42" in block
        assert "fear" in block
        assert "17" in block
        assert "headline_sentiment" in block

    def test_supports_flat_n_texts_alongside_nested_extras(self) -> None:
        snapshot = {"value": 0.3, "label": "greed", "n_texts": 8}
        block = format_news_sentiment_block(snapshot)
        assert block is not None
        assert "+0.30" in block
        assert "greed" in block
        assert "8" in block

    def test_surfaces_llm_macro_impact_when_blend_contributed(self) -> None:
        """When the LLM macro pass moved the signal, the explainer must see it."""
        snapshot = {
            "value": 0.85,
            "label": "greed",
            "source": "headline_sentiment",
            "extras": {
                "n_texts": 12,
                "news_blend_source": "llm",
                "news_impact_value": 0.85,
                "news_impact_n": 2,
                "news_blend_conflict": False,
            },
        }
        block = format_news_sentiment_block(snapshot)
        assert block is not None
        assert "Macro news impact" in block
        assert "+0.85" in block
        assert "2" in block  # macro headline count
        assert "CONFLICT" not in block

    def test_surfaces_finbert_vs_llm_conflict_warning(self) -> None:
        """A bullish-tone vs bearish-macro disagreement must be called out, not buried."""
        snapshot = {
            "value": 0.1,
            "label": "neutral",
            "source": "headline_sentiment",
            "extras": {
                "n_texts": 10,
                "news_blend_source": "blended",
                "news_impact_value": -0.8,
                "news_impact_n": 1,
                "news_blend_conflict": True,
            },
        }
        block = format_news_sentiment_block(snapshot)
        assert block is not None
        assert "CONFLICT" in block

    def test_pure_finbert_snapshot_adds_no_macro_or_conflict_lines(self) -> None:
        """Backward-compatible: no LLM contribution → no extra lines (Phase 1 shape)."""
        snapshot = {
            "value": -0.3,
            "label": "fear",
            "source": "headline_sentiment",
            "extras": {
                "n_texts": 9,
                "news_blend_source": "finbert",
                "news_impact_value": 0.0,
                "news_impact_n": 0,
                "news_blend_conflict": False,
            },
        }
        block = format_news_sentiment_block(snapshot)
        assert block is not None
        assert "Macro news impact" not in block
        assert "CONFLICT" not in block
        # Pin the exact Phase-1 shape: header + score + label + texts + source = 5 lines.
        assert len(block.splitlines()) == 5


class TestOnChainBlock:
    def test_returns_none_when_snapshot_empty(self) -> None:
        assert format_onchain_block(None) is None
        assert format_onchain_block({}) is None

    def test_skipped_for_unsupported_pair(self) -> None:
        snapshot = {
            "asset_scope": "unsupported_pair",
            "metrics": {"mvrv": {"value": 2.1}},
            "signal": {"action": "HOLD", "confidence": 0.0},
        }
        assert format_onchain_block(snapshot) is None

    def test_skipped_when_provider_none_and_unavailable(self) -> None:
        snapshot = {
            "asset_scope": "btc",
            "provider": "none",
            "unavailable_reason": "no_snapshot_yet",
            "signal": {"action": "HOLD", "confidence": 0.0},
            "metrics": {},
        }
        assert format_onchain_block(snapshot) is None

    def test_skipped_when_metrics_block_has_no_values(self) -> None:
        snapshot = {
            "asset_scope": "btc",
            "provider": "glassnode",
            "metrics": {"mvrv": None, "sopr": None, "exchange_flow": None},
            "signal": {"action": "HOLD", "confidence": 0.5},
        }
        assert format_onchain_block(snapshot) is None

    def test_emits_block_with_all_metrics(self) -> None:
        snapshot = {
            "asset_scope": "btc",
            "provider": "glassnode",
            "stale": False,
            "signal": {"action": "BUY", "confidence": 0.7},
            "metrics": {
                "mvrv": {"value": 1.85, "z_score": -0.42, "label": "neutral"},
                "sopr": {"value": 1.02, "z_score": 0.15, "label": "neutral"},
                "exchange_flow": {"value": -12345.0, "z_score": -1.8, "label": "accumulation"},
            },
        }
        block = format_onchain_block(snapshot)
        assert block is not None
        assert "## On-chain metrics (BTC)" in block
        assert "BUY" in block
        assert "MVRV" in block
        assert "SOPR" in block
        assert "Exchange flow" in block
        assert "accumulation" in block
        assert "glassnode" in block

    def test_stale_note_appears_when_stale_true(self) -> None:
        snapshot = {
            "asset_scope": "btc",
            "provider": "glassnode",
            "stale": True,
            "signal": {"action": "HOLD", "confidence": 0.4},
            "metrics": {"mvrv": {"value": 2.0}},
        }
        block = format_onchain_block(snapshot)
        assert block is not None
        assert "stale" in block.lower()


class TestRegistryGating:
    def test_onchain_is_registered_and_pro_gated(self) -> None:
        section = get_section("onchain")
        assert section is not None
        assert section.requires_tier == SubscriptionTier.PRO

    def test_news_sentiment_is_registered_no_tier_gate(self) -> None:
        section = get_section("news_sentiment")
        assert section is not None
        assert section.requires_tier is None

    def test_free_user_does_not_see_onchain(self) -> None:
        visible = {s.key for s in iter_effective_sections(enabled_keys=None, user_tier=SubscriptionTier.FREE)}
        assert "onchain" not in visible
        assert "news_sentiment" in visible

    def test_starter_user_does_not_see_onchain(self) -> None:
        visible = {s.key for s in iter_effective_sections(enabled_keys=None, user_tier=SubscriptionTier.STARTER)}
        assert "onchain" not in visible

    def test_pro_user_sees_onchain(self) -> None:
        visible = {s.key for s in iter_effective_sections(enabled_keys=None, user_tier=SubscriptionTier.PRO)}
        assert "onchain" in visible

    def test_elite_user_sees_onchain(self) -> None:
        visible = {s.key for s in iter_effective_sections(enabled_keys=None, user_tier=SubscriptionTier.ELITE)}
        assert "onchain" in visible
