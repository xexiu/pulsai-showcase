"""
AI Sources Configuration Loader (Sprint 1.7)

Loads and validates ai-sources.yaml configuration.

WHY YAML CONFIG?
- Easy to audit and review curated sources
- Version controlled (changes tracked in git)
- No runtime modification (security)
- Clear documentation of allowed sources

SECURITY:
- Only sources in config are allowed
- Prohibited sources list prevents known bad actors
- AI guardrails enforce safe behavior
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Path to ai-sources.yaml relative to apps/api
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "ai-sources.yaml"

# Headline RSS worker: only these external source types may set headline_ingestion: true (fail-fast).
# - blog_rss: third-party blogs with a real RSS/Atom URL
# - government_rss: official press/release RSS (e.g. Fed, BLS) — still HTTP RSS, not HTML calendar pages
# - news_rss: mainstream financial media RSS/Atom (must use rss_url — site homepages are not feeds)
HEADLINE_RSS_ALLOWED_TYPES: frozenset[str] = frozenset({"blog_rss", "government_rss", "news_rss"})

_HEADLINE_FETCH_PRIORITY_HIGH = "high"
_HEADLINE_FETCH_PRIORITY_LOW = "low"


def _headline_source_sort_key(source: dict[str, Any]) -> tuple[int, str]:
    """Breaking/market wires first; official slow feeds (Fed press releases) last."""
    priority = source.get("headline_fetch_priority")
    if priority == _HEADLINE_FETCH_PRIORITY_HIGH:
        bucket = 0
    elif priority == _HEADLINE_FETCH_PRIORITY_LOW:
        bucket = 2
    else:
        bucket = 1
    return (bucket, str(source.get("name", "")))


@lru_cache(maxsize=1)
def load_ai_sources_config() -> dict[str, Any]:
    """
    Load ai-sources.yaml configuration.

    Returns cached config after first load (immutable at runtime).

    Returns:
        Configuration dictionary with:
        - internal_sources: PulsAI's own data sources
        - external_sources: Curated external sources
        - prohibited_sources: Blocked sources
        - ai_guardrails: Safety settings
        - context_templates: Prompt templates

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config is invalid YAML
    """
    if not CONFIG_PATH.exists():
        logger.error("AI sources config not found: %s", CONFIG_PATH)
        raise FileNotFoundError(f"AI sources config not found: {CONFIG_PATH}")

    logger.info("Loading AI sources config from: %s", CONFIG_PATH)

    with CONFIG_PATH.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Validate required sections
    _validate_config(config)

    logger.info(
        "AI sources config loaded: %d internal, %d external sources",
        len(config.get("internal_sources", {}).get("include", [])),
        len(config.get("external_sources", {}).get("sources", [])),
    )

    result: dict[str, Any] = config
    return result


def _validate_headline_ingestion_flags(sources: list[dict[str, Any]]) -> None:
    """Fail-fast: headline_ingestion only with allowed RSS-capable types."""
    for source in sources:
        raw_flag = source.get("headline_ingestion")
        if raw_flag is not True:
            continue
        stype = source.get("type")
        if stype not in HEADLINE_RSS_ALLOWED_TYPES:
            name = source.get("name", "?")
            raise ValueError(
                f"ai-sources.yaml: '{name}' has headline_ingestion: true but type {stype!r} is not "
                f"allowed for headline RSS (allowed: {sorted(HEADLINE_RSS_ALLOWED_TYPES)})"
            )
        max_items = source.get("headline_max_items")
        if max_items is not None and (not isinstance(max_items, int) or max_items < 1):
            raise ValueError(f"ai-sources.yaml: '{source.get('name', '?')}' headline_max_items must be a positive int")


def _validate_config(config: dict[str, Any]) -> None:
    """
    Validate ai-sources.yaml structure.

    Raises:
        ValueError: If required sections are missing or invalid
    """
    required_sections = ["version", "internal_sources", "external_sources", "ai_guardrails"]

    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section in ai-sources.yaml: {section}")

    # Validate guardrails have required fields
    guardrails = config["ai_guardrails"]
    required_guardrails = ["max_context_tokens", "temperature", "refuse_if_no_data"]

    for field in required_guardrails:
        if field not in guardrails:
            raise ValueError(f"Missing required guardrail: {field}")

    # Validate external sources have required fields
    sources = config["external_sources"].get("sources", [])
    for source in sources:
        if "name" not in source or "url" not in source:
            raise ValueError(f"External source missing name or url: {source}")

    _validate_headline_ingestion_flags(sources)


def get_external_sources() -> list[dict[str, Any]]:
    """Get list of curated external sources."""
    config = load_ai_sources_config()
    external = config.get("external_sources", {})

    if not external.get("enabled", False):
        return []

    result: list[dict[str, Any]] = external.get("sources", [])
    return result


def get_headline_rss_sources() -> list[dict[str, Any]]:
    """
    External sources enabled for headline sentiment RSS fetch.

    Precondition: ai-sources.yaml validated at load (headline_ingestion + type allowlist).
    """
    rows = [s for s in get_external_sources() if s.get("headline_ingestion") is True and s.get("type") in HEADLINE_RSS_ALLOWED_TYPES]
    rows = sorted(rows, key=_headline_source_sort_key)
    if rows:
        names = [str(s.get("name", "?")) for s in rows]
        logger.debug("[headline_rss] config_curated count=%d names=%s", len(rows), names)
    else:
        logger.warning("[headline_rss] config_curated count=0 (no headline_ingestion sources)")
    return rows


def get_ai_guardrails() -> dict[str, Any]:
    """Get AI guardrails configuration."""
    config = load_ai_sources_config()
    result: dict[str, Any] = config.get("ai_guardrails", {})
    return result


def get_context_template(template_name: str) -> str:
    """
    Get a specific context template.

    Args:
        template_name: Name of template (signal_explanation, chart_analysis, etc.)

    Returns:
        Template string or empty string if not found
    """
    config = load_ai_sources_config()
    templates = config.get("context_templates", {})
    result: str = templates.get(template_name, "")
    return result


def is_source_prohibited(url: str) -> bool:
    """
    Check if a URL is from a prohibited source.

    Args:
        url: URL to check

    Returns:
        True if source is prohibited, False otherwise
    """
    config = load_ai_sources_config()
    prohibited = config.get("prohibited_sources", [])

    url_lower = url.lower()
    for item in prohibited:
        domain = item.get("domain", "").lower()
        if domain and domain in url_lower:
            return True

    return False
