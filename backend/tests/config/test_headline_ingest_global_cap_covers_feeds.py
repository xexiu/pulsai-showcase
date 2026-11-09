"""Global ingest cap must cover the curated per-feed budgets (no silent starvation)."""

from __future__ import annotations

from typing import Any

import yaml

from src.infrastructure.config.settings import settings
from tests.helpers.api_paths import API_ROOT

_CONFIG = API_ROOT / "config" / "ai-sources.yaml"


def _sum_configured_headline_max_items() -> int:
    total = 0

    def walk(node: Any) -> None:
        nonlocal total
        if isinstance(node, dict):
            if node.get("rss_url") and node.get("headline_ingestion"):
                raw = node.get("headline_max_items")
                if isinstance(raw, int) and raw > 0:
                    total += raw
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(yaml.safe_load(_CONFIG.read_text(encoding="utf-8")))
    return total


def test_global_ingest_cap_covers_sum_of_per_feed_budgets() -> None:
    """REGRESSION: 56 < sum(max_items)=96 starved later feeds after Investing macro RSS adds."""
    budgeted = _sum_configured_headline_max_items()
    assert settings.headline_ingestion_global_max_items >= budgeted, (
        f"headline_ingestion_global_max_items={settings.headline_ingestion_global_max_items} "
        f"< sum(headline_max_items)={budgeted}; later-sorted feeds (crypto / macro RSS) get truncated"
    )
