"""Headline ingestion flags on ai-sources.yaml (fail-fast validation)."""

from __future__ import annotations

import pytest

from src.infrastructure.ai.sources_loader import (
    HEADLINE_RSS_ALLOWED_TYPES,
    _validate_headline_ingestion_flags,
    get_headline_rss_sources,
    load_ai_sources_config,
)


def test_validate_headline_ingestion_rejects_non_rss_type() -> None:
    with pytest.raises(ValueError, match="not allowed for headline RSS"):
        _validate_headline_ingestion_flags(
            [
                {
                    "name": "Bad",
                    "url": "https://x.com/a",
                    "type": "twitter_feed",
                    "headline_ingestion": True,
                },
            ]
        )


def test_validate_headline_ingestion_accepts_blog_rss() -> None:
    _validate_headline_ingestion_flags(
        [
            {
                "name": "Good",
                "url": "https://example.com/blog",
                "type": "blog_rss",
                "headline_ingestion": True,
                "headline_max_items": 10,
            },
        ]
    )


def test_validate_headline_ingestion_accepts_government_rss() -> None:
    _validate_headline_ingestion_flags(
        [
            {
                "name": "Gov",
                "url": "https://www.example.gov/news/",
                "type": "government_rss",
                "headline_ingestion": True,
                "headline_max_items": 5,
            },
        ]
    )


def test_validate_headline_ingestion_accepts_news_rss() -> None:
    _validate_headline_ingestion_flags(
        [
            {
                "name": "News",
                "url": "https://www.example.com",
                "rss_url": "https://www.example.com/feed.xml",
                "type": "news_rss",
                "headline_ingestion": True,
                "headline_max_items": 4,
            },
        ]
    )


def test_validate_headline_max_items_must_be_positive() -> None:
    with pytest.raises(ValueError, match="headline_max_items"):
        _validate_headline_ingestion_flags(
            [
                {
                    "name": "Bad",
                    "url": "https://example.com/feed",
                    "type": "blog_rss",
                    "headline_ingestion": True,
                    "headline_max_items": 0,
                },
            ]
        )


def test_allowed_types_frozen() -> None:
    assert "blog_rss" in HEADLINE_RSS_ALLOWED_TYPES
    assert "government_rss" in HEADLINE_RSS_ALLOWED_TYPES
    assert "news_rss" in HEADLINE_RSS_ALLOWED_TYPES
    assert "twitter_feed" not in HEADLINE_RSS_ALLOWED_TYPES


def test_get_headline_rss_sources_includes_fed_and_bls_rss() -> None:
    load_ai_sources_config.cache_clear()
    rows = get_headline_rss_sources()
    names = {r.get("name") for r in rows}
    assert "Federal Reserve Board Press Releases" in names
    assert "BLS Latest News Releases" in names
    assert "Financial Times (International)" in names
    allowed = {"blog_rss", "government_rss", "news_rss"}
    assert all(r.get("type") in allowed for r in rows)


def test_get_headline_rss_sources_prioritizes_breaking_feeds_first() -> None:
    load_ai_sources_config.cache_clear()
    rows = get_headline_rss_sources()
    assert rows, "expected curated headline sources"
    high_names = [str(r.get("name")) for r in rows if r.get("headline_fetch_priority") == "high"]
    assert high_names, "expected at least one high-priority breaking feed in ai-sources.yaml"
    first_high = rows.index(next(r for r in rows if r.get("headline_fetch_priority") == "high"))
    first_fed = next(
        (i for i, r in enumerate(rows) if "Federal Reserve Board Press Releases" in str(r.get("name"))),
        None,
    )
    assert first_fed is not None
    assert first_high < first_fed
