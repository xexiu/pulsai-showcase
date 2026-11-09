"""Behavior tests for the multi-timeframe confluence explainer context.

- The confluence header block narrates the combined directional picture and flags
  conflict (echoing the FinBERT-vs-LLM conflict surfacing).
- build_confluence_explain_context assembles ONE context: confluence header +
  condensed per-timeframe signal headers + the shared news/on-chain sections once.
"""

from __future__ import annotations

from src.domain.services.confluence_explain_summary import ConfluenceLeg, summarize_confluence
from src.infrastructure.ai.rag_context import build_confluence_explain_context
from src.infrastructure.ai.rag_explain_signal_sections import format_confluence_header_block


def _summary(symbol: str, *pairs: tuple[str, str, float]):
    legs = [ConfluenceLeg(timeframe=tf, action=a, confidence=c) for tf, a, c in pairs]
    return summarize_confluence(symbol, legs)


class TestConfluenceHeaderBlock:
    def test_lists_timeframes_and_dominant(self) -> None:
        summary = _summary("BTC/USDT", ("1h", "BUY", 0.8), ("4h", "BUY", 0.6))
        block = format_confluence_header_block(summary)
        assert "## Multi-Timeframe Confluence" in block
        assert "BTC/USDT" in block
        assert "1h" in block
        assert "4h" in block
        assert "BUY" in block
        assert "CONFLICT" not in block  # unanimous → no conflict line

    def test_flags_conflict_when_timeframes_disagree(self) -> None:
        summary = _summary("BTC/USDT", ("1h", "BUY", 0.8), ("4h", "SELL", 0.7))
        block = format_confluence_header_block(summary)
        assert "CONFLICT" in block

    def test_mixed_split_is_described(self) -> None:
        summary = _summary("ETH/USDT", ("1h", "BUY", 0.6), ("4h", "SELL", 0.9))
        block = format_confluence_header_block(summary)
        assert "MIXED" in block


class TestBuildConfluenceExplainContext:
    def _signal_dict(self, tf: str, action: str, price: float) -> dict:
        return {
            "symbol": "BTC/USDT",
            "action": action,
            "confidence": 0.8,
            "timeframe": tf,
            "model_version": "v1",
            "price": price,
            "signal_type": "ml",
            "meta_score": 0.3,
        }

    def test_assembles_header_per_tf_headers_and_news_once(self) -> None:
        summary = _summary("BTC/USDT", ("1h", "BUY", 0.8), ("4h", "BUY", 0.6))
        signals = [self._signal_dict("1h", "BUY", 50000.0), self._signal_dict("4h", "BUY", 50000.0)]
        news = {"value": 0.6, "label": "greed", "source": "headline_sentiment", "extras": {"n_texts": 12}}

        ctx = build_confluence_explain_context(summary, signals, news_sentiment=news)

        assert "## Multi-Timeframe Confluence" in ctx
        # both per-TF signal headers present
        assert ctx.count("## Signal Data (ML headline)") == 2
        assert "1h" in ctx
        assert "4h" in ctx
        # shared news section appears exactly once
        assert ctx.count("## News sentiment (aggregate)") == 1

    def test_skips_legs_without_a_matching_signal_dict(self) -> None:
        summary = _summary("BTC/USDT", ("1h", "BUY", 0.8), ("4h", "BUY", 0.6))
        signals = [self._signal_dict("1h", "BUY", 50000.0)]  # 4h missing
        ctx = build_confluence_explain_context(summary, signals)
        assert ctx.count("## Signal Data (ML headline)") == 1

    def test_no_news_or_onchain_still_builds(self) -> None:
        summary = _summary("BTC/USDT", ("1h", "BUY", 0.8))
        ctx = build_confluence_explain_context(summary, [self._signal_dict("1h", "BUY", 50000.0)])
        assert "## Multi-Timeframe Confluence" in ctx
        assert "## News sentiment" not in ctx
