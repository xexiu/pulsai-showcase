"""
News-sentiment, on-chain and external-news blocks of the signal-explain RAG context.

IMPORTERS/CALLERS: rag_explain_signal_sections (section registry), rag_context, tests/infrastructure/ai/test_rag_news_onchain_sections.
AFFECTED API: none (prompt text only).
DATA SCHEMAS: none.

Split out of rag_explain_signal_sections.py (P1-8b) to respect module line limits.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_EXTERNAL_NEWS_ITEMS = 5


def format_news_sentiment_block(snapshot: dict[str, Any] | None) -> str | None:
    """Aggregate news-sentiment snapshot (normalized -1..+1 with label).

    Skipped when the snapshot has no analyzed texts (placeholder) to avoid
    feeding the LLM a meaningless "neutral, 0 sources" line.
    """
    if not snapshot:
        logger.debug("format_news_sentiment_block: skipped (no analyzed texts or empty snapshot)")
        return None

    extras = snapshot.get("extras")
    extras = extras if isinstance(extras, dict) else {}

    n_texts_raw = snapshot.get("n_texts")
    if n_texts_raw is None:
        n_texts_raw = extras.get("n_texts")
    try:
        n_texts = int(n_texts_raw) if n_texts_raw is not None else 0
    except TypeError, ValueError:
        n_texts = 0
    if n_texts <= 0:
        return None

    value = snapshot.get("value")
    label = snapshot.get("label")
    source = snapshot.get("source", "headline_sentiment")

    lines = ["## News sentiment (aggregate)"]
    if isinstance(value, (int, float)):
        lines.append(f"- Normalized score: {float(value):+.2f} (scale: -1.0 fear → +1.0 greed)")
    if label:
        lines.append(f"- Label: {label}")
    lines.append(f"- Analyzed texts: {n_texts}")
    lines.append(f"- Source: {source}")
    lines.extend(_news_impact_lines(extras))
    return "\n".join(lines)


def _news_impact_lines(extras: dict[str, Any]) -> list[str]:
    """Extra lines surfacing the LLM macro-impact pass (Phase 2) when it contributed.

    FinBERT scores tone and is blind to macro/geopolitical impact; the snapshot's
    LLM macro pass fills that gap. We expose its contribution + any FinBERT-vs-LLM
    conflict so the explanation can cite the macro read and warn on disagreement
    (the trading SYSTEM_PROMPT already requires calling out component disagreement).
    Returns [] for pure-FinBERT snapshots (no LLM contribution) — backward-compatible.
    """
    blend_source = extras.get("news_blend_source")
    impact_value = extras.get("news_impact_value")
    # Macro line only when the LLM actually contributed. A conflict cannot exist
    # without LLM contribution (it needs both sides directional), so the conflict
    # line is nested here — that also prevents an orphaned warning with no referent.
    if blend_source not in ("llm", "blended") or not isinstance(impact_value, (int, float)):
        return []
    impact_n_raw = extras.get("news_impact_n")
    impact_n = impact_n_raw if isinstance(impact_n_raw, int) and not isinstance(impact_n_raw, bool) else 0
    lines = [f"- Macro news impact (LLM, FinBERT's blind spot): {float(impact_value):+.2f} from {impact_n} macro headline(s) [{blend_source}]"]
    if bool(extras.get("news_blend_conflict")):
        lines.append("- CONFLICT: crypto-tone and macro-news signals point opposite ways — weight this cautiously.")
    return lines


def _onchain_metric_row(label: str, entry: dict[str, Any] | None) -> str | None:
    """Render one on-chain metric line; None if value is missing or non-numeric."""
    if not isinstance(entry, dict):
        logger.debug("_onchain_metric_row: skipped (metric missing or non-numeric)")
        return None
    value = entry.get("value")
    if not isinstance(value, (int, float)):
        return None
    parts = [f"value={float(value):.4g}"]
    z = entry.get("z_score")
    if isinstance(z, (int, float)):
        parts.append(f"z={float(z):+.2f}")
    elabel = entry.get("label")
    if elabel:
        parts.append(f"label={elabel}")
    return f"- {label}: " + ", ".join(parts)


_ONCHAIN_METRIC_KEYS: tuple[tuple[str, str], ...] = (
    ("MVRV", "mvrv"),
    ("SOPR", "sopr"),
    ("Exchange flow", "exchange_flow"),
)


def _onchain_snapshot_is_usable(snapshot: dict[str, Any]) -> bool:
    """Gate: BTC pair, provider not 'none', has a metrics dict."""
    if snapshot.get("asset_scope") == "unsupported_pair":
        return False
    if snapshot.get("unavailable_reason") and snapshot.get("provider") == "none":
        return False
    return isinstance(snapshot.get("metrics"), dict)


def format_onchain_block(snapshot: dict[str, Any] | None) -> str | None:
    """On-chain metrics (MVRV / SOPR / exchange flow) from the worker snapshot.

    Skipped for unsupported pairs, stale-without-data, or when no metrics are present.
    Per-metric row formatting + usability gate are extracted as helpers for SRP
    and to keep the branch count under the linter ceiling.
    """
    if not snapshot or not _onchain_snapshot_is_usable(snapshot):
        logger.debug("format_onchain_block: skipped (snapshot unusable or no metrics)")
        return None

    metrics: dict[str, Any] = snapshot["metrics"]
    metric_rows = [row for label, key in _ONCHAIN_METRIC_KEYS if (row := _onchain_metric_row(label, metrics.get(key))) is not None]
    if not metric_rows:
        return None

    lines = ["## On-chain metrics (BTC)"]
    signal = snapshot.get("signal")
    if isinstance(signal, dict):
        action = signal.get("action")
        conf = signal.get("confidence")
        if action and isinstance(conf, (int, float)):
            lines.append(f"- On-chain signal: {action} (confidence {float(conf):.0%})")
    lines.extend(metric_rows)
    provider = snapshot.get("provider")
    if provider:
        lines.append(f"- Provider: {provider}")
    if snapshot.get("stale"):
        lines.append("- Note: snapshot is stale (last-good cached)")
    return "\n".join(lines)


def format_external_news_block(
    news: list[dict[str, Any]] | None,
    *,
    cite_sources: bool = True,
) -> str | None:
    if not news:
        logger.debug("format_external_news_block: skipped (no news headlines)")
        return None
    lines = ["## Relevant Market News"]
    for item in news[:MAX_EXTERNAL_NEWS_ITEMS]:
        source = item.get("source", "Unknown")
        headline = item.get("headline", "")
        if not headline:
            continue
        if cite_sources:
            lines.append(f"- [{source}] {headline}")
        else:
            lines.append(f"- {headline}")
    if len(lines) == 1:
        return None
    return "\n".join(lines)
