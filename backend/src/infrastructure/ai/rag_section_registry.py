"""
RAG context section registry — single source of truth for what can appear
in a signal-explain prompt.

Each "section" is a self-contained block (e.g. weighted consensus, classic TA,
on-chain proxies) with a stable `key`, human metadata, optional tier gate,
and a `build` function that produces the section text from `SectionInputs`.

Adding a new section is one file: declare a `ContextSection`, append to
`DEFAULT_SECTIONS`, and the admin UI auto-discovers it (Phase 4).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from src.domain.enums import SubscriptionTier


@dataclass(frozen=True)
class SectionInputs:
    """All per-request inputs available to section builders.

    Carried as a single immutable bundle so section signatures stay stable
    when new fields are added.
    """

    signal: dict[str, Any]
    indicators: dict[str, Any] | None = None
    model_metrics: dict[str, Any] | None = None
    recent_candles: list[dict[str, Any]] | None = None
    external_news: list[dict[str, Any]] | None = None
    signal_type: str | None = None
    classic_sources: dict[str, bool] | None = None
    model_votes: list[dict[str, Any]] | None = None
    meta_score: float | None = None
    feature_importance: dict[str, Any] | None = None
    suggested_position_pct: float | None = None
    onchain: dict[str, Any] | None = None
    news_sentiment: dict[str, Any] | None = None
    cite_sources: bool = True
    # Per-bar ML feature vector. Carries the ``dist_to_support_N`` /
    # ``dist_to_resistance_N`` / ``atr_N`` values that the technical-levels
    # section + the target-price helper need to anchor BUY/SELL Conclusion
    # targets to real support/resistance gaps instead of the entry price.
    model_input_features: dict[str, Any] | None = None


@dataclass(frozen=True)
class ContextSection:
    """A registered prompt section.

    `requires_tier=None` means available to all tiers. Otherwise the section is
    silently dropped for users below the required tier, even when enabled globally.
    """

    key: str
    display_name: str
    description: str
    build: Callable[[SectionInputs], str | None]
    default_enabled: bool = True
    requires_tier: SubscriptionTier | None = None


@dataclass
class _SectionRegistry:
    """Ordered registry. Order = order in the final prompt."""

    sections: list[ContextSection] = field(default_factory=list)
    _by_key: dict[str, ContextSection] = field(default_factory=dict)

    def register(self, section: ContextSection) -> None:
        if section.key in self._by_key:
            raise ValueError(f"Duplicate section key: {section.key!r}")
        self.sections.append(section)
        self._by_key[section.key] = section

    def all_sections(self) -> tuple[ContextSection, ...]:
        return tuple(self.sections)

    def get(self, key: str) -> ContextSection | None:
        return self._by_key.get(key)

    def iter_effective(
        self,
        *,
        enabled_keys: set[str] | None,
        user_tier: SubscriptionTier | str | None,
    ) -> Iterable[ContextSection]:
        """Yield sections honoring the global enabled set + the user tier gate.

        - ``enabled_keys=None`` → respect each section's ``default_enabled`` (legacy/no-config path).
        - ``enabled_keys=set(...)`` → only sections whose key is in the set.
        - Tier gate: sections with ``requires_tier`` are dropped if ``user_tier`` is
          missing or below the required tier.

        ``user_tier`` accepts both :class:`SubscriptionTier` and the raw string
        form (``"free"``, ``"pro"``, …) because SQLAlchemy's
        ``UserModel.subscription_tier`` is ``Mapped[str]`` and ORM-hydrated
        users hand back the raw value. Coercion goes through the SoT
        :meth:`SubscriptionTier.coerce` so the logic lives in exactly one
        place across this module and ``AIExplainConfigService``.
        """
        tier_enum = SubscriptionTier.coerce(user_tier)
        for section in self.sections:
            if enabled_keys is None:
                if not section.default_enabled:
                    continue
            elif section.key not in enabled_keys:
                continue

            if section.requires_tier is not None and (tier_enum is None or not tier_enum.can_access(section.requires_tier)):
                continue

            yield section


_REGISTRY = _SectionRegistry()


def register_section(section: ContextSection) -> None:
    _REGISTRY.register(section)


def all_sections() -> tuple[ContextSection, ...]:
    return _REGISTRY.all_sections()


def get_section(key: str) -> ContextSection | None:
    return _REGISTRY.get(key)


def iter_effective_sections(
    *,
    enabled_keys: set[str] | None,
    user_tier: SubscriptionTier | str | None,
) -> Iterable[ContextSection]:
    return _REGISTRY.iter_effective(enabled_keys=enabled_keys, user_tier=user_tier)
