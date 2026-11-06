"""Behavior pins for the RAG section registry.

These tests guard:
1. The registry contains the 9 default sections, in the documented order.
2. The full-input `build_signal_context()` output preserves section order
   and emits every populated block (registry parity with pre-refactor).
3. `enabled_keys` filtering drops sections cleanly.
4. Tier gating drops `requires_tier` sections for tiers below the requirement.

If a future PR adds/removes/reorders sections, these tests force the change
to be intentional (and to update the expected order list here).
"""

from __future__ import annotations

import pytest

from src.domain.enums import SubscriptionTier
from src.infrastructure.ai.rag_context import RAGContextBuilder
from src.infrastructure.ai.rag_section_registry import (
    ContextSection,
    SectionInputs,
    all_sections,
    get_section,
    iter_effective_sections,
    register_section,
)

EXPECTED_DEFAULT_ORDER: tuple[str, ...] = (
    "signal_header",
    "weighted_consensus",
    "classic_sources",
    "feature_importance",
    "position_sizing",
    "indicators",
    "model_metrics",
    "recent_candles",
    "external_news",
)


@pytest.fixture
def full_signal_inputs() -> dict[str, object]:
    """Inputs that populate every default section so we can assert order/parity."""
    return {
        "signal": {
            "id": "sig-1",
            "symbol": "BTC/USDT",
            "action": "BUY",
            "confidence": 0.82,
            "timeframe": "1h",
            "model_version": "v1.2.3",
            "price": 50000.0,
            "created_at": "2026-05-24T08:00:00Z",
        },
        "indicators": {
            "rsi": 28.0,
            "macd": {"value": 0.5, "signal": 0.3, "histogram": 0.2},
            "bb": {"upper": 51000, "middle": 50000, "lower": 49000},
            "price": 50000.0,
            "ema_50": 49500.0,
        },
        "model_metrics": {"accuracy": 0.65, "sharpe": 1.8, "win_rate": 0.58},
        "recent_candles": [
            {"high": 50500, "low": 49500, "close": 49800},
            {"high": 50800, "low": 49900, "close": 50200},
        ],
        "external_news": [{"source": "Reuters", "headline": "BTC ETF inflows surge"}],
        "signal_type": "ml_ensemble",
        "classic_sources": {"rsi_oversold": True, "macd_crossover": True, "bb_squeeze": False},
        "model_votes": [
            {"model_type": "lgbm", "action": "BUY", "confidence": 0.85, "weight": 0.6, "model_version": "lgbm-v1"},
            {"model_type": "rf", "action": "BUY", "confidence": 0.75, "weight": 0.4, "model_version": "rf-v2"},
        ],
        "meta_score": 0.42,
        "feature_importance": {"rsi": 0.31, "macd_hist": 0.22, "volume_zscore": 0.18},
        "suggested_position_pct": 0.05,
    }


class TestRegistryShape:
    def test_default_registry_has_expected_sections_in_order(self) -> None:
        actual_keys = tuple(s.key for s in all_sections())
        # The registry may contain MORE than the defaults if Phase 3 sections
        # are already registered (e.g. onchain). We assert the defaults appear
        # in the documented order as a contiguous subsequence.
        keys_set = set(actual_keys)
        missing = [k for k in EXPECTED_DEFAULT_ORDER if k not in keys_set]
        assert missing == [], f"Missing default sections: {missing}"

        # Order: every default key must appear in the same relative order.
        positions = [actual_keys.index(k) for k in EXPECTED_DEFAULT_ORDER]
        assert positions == sorted(positions), f"Default sections are out of order. Got: {[actual_keys[i] for i in positions]}"

    def test_each_default_section_has_metadata(self) -> None:
        for key in EXPECTED_DEFAULT_ORDER:
            section = get_section(key)
            assert section is not None, f"Section {key} not registered"
            assert section.display_name, f"{key} missing display_name"
            assert section.description, f"{key} missing description"
            assert callable(section.build), f"{key}.build is not callable"

    def test_duplicate_registration_raises(self) -> None:
        duplicate = ContextSection(
            key="signal_header",  # already registered
            display_name="dup",
            description="dup",
            build=lambda _: None,
        )
        with pytest.raises(ValueError, match="Duplicate section key"):
            register_section(duplicate)


class TestBuilderRegistryParity:
    def test_full_inputs_emit_every_default_section_header(self, full_signal_inputs: dict[str, object]) -> None:
        builder = RAGContextBuilder()
        context = builder.build_signal_context(SectionInputs(**full_signal_inputs))  # type: ignore[arg-type]

        # Every default section's leading markdown header must appear.
        expected_headers = [
            "## Signal Data (ML headline)",
            "## Weighted consensus",
            "## Classic / rule-based TA",
            "## ML feature influence",
            "## Position sizing",
            "## Technical indicators (canonical TA)",
            "## Sentiment, on-chain proxies",  # supplementary inside the indicators block
            "## Model Performance",
            "## Recent Price Action",
            "## Relevant Market News",
        ]
        for header in expected_headers:
            assert header in context, f"Missing header: {header!r}"

    def test_section_order_in_output_matches_registry_order(self, full_signal_inputs: dict[str, object]) -> None:
        builder = RAGContextBuilder()
        context = builder.build_signal_context(SectionInputs(**full_signal_inputs))  # type: ignore[arg-type]

        # Check that the *first* header of each section appears in registry order.
        header_for_key: dict[str, str] = {
            "signal_header": "## Signal Data (ML headline)",
            "weighted_consensus": "## Weighted consensus",
            "classic_sources": "## Classic / rule-based TA",
            "feature_importance": "## ML feature influence",
            "position_sizing": "## Position sizing",
            "indicators": "## Technical indicators (canonical TA)",
            "model_metrics": "## Model Performance",
            "recent_candles": "## Recent Price Action",
            "external_news": "## Relevant Market News",
        }
        positions: list[tuple[str, int]] = []
        for key in EXPECTED_DEFAULT_ORDER:
            header = header_for_key[key]
            idx = context.find(header)
            assert idx >= 0, f"Header for {key} not found"
            positions.append((key, idx))
        sorted_by_pos = sorted(positions, key=lambda t: t[1])
        assert [k for k, _ in sorted_by_pos] == list(EXPECTED_DEFAULT_ORDER)


class TestEnabledKeysFiltering:
    def test_subset_of_enabled_keys_drops_unlisted_sections(self, full_signal_inputs: dict[str, object]) -> None:
        builder = RAGContextBuilder()
        context = builder.build_signal_context(
            SectionInputs(**full_signal_inputs),  # type: ignore[arg-type]
            enabled_section_keys={"signal_header", "indicators"},
        )
        assert "## Signal Data (ML headline)" in context
        assert "## Technical indicators (canonical TA)" in context
        # Dropped:
        assert "## Weighted consensus" not in context
        assert "## Relevant Market News" not in context
        assert "## Model Performance" not in context

    def test_empty_enabled_set_emits_only_template_no_sections(self, full_signal_inputs: dict[str, object]) -> None:
        builder = RAGContextBuilder()
        context = builder.build_signal_context(
            SectionInputs(**full_signal_inputs),  # type: ignore[arg-type]
            enabled_section_keys=set(),
        )
        for key in EXPECTED_DEFAULT_ORDER:
            header = get_section(key)
            assert header is not None
        # No section headers should appear.
        assert "## Signal Data (ML headline)" not in context
        assert "## Weighted consensus" not in context


class TestTierGating:
    def test_section_with_tier_dropped_for_lower_tier(self) -> None:
        # Register an ephemeral PRO-only section for the test, then ensure it is
        # filtered out for FREE/STARTER users.
        marker_key = "_test_tier_gated_section"
        if get_section(marker_key) is None:
            register_section(
                ContextSection(
                    key=marker_key,
                    display_name="Test gated",
                    description="ephemeral",
                    build=lambda _: "## Gated Marker\n- present",
                    requires_tier=SubscriptionTier.PRO,
                )
            )
        free_visible = [s.key for s in iter_effective_sections(enabled_keys=None, user_tier=SubscriptionTier.FREE)]
        pro_visible = [s.key for s in iter_effective_sections(enabled_keys=None, user_tier=SubscriptionTier.PRO)]
        assert marker_key not in free_visible
        assert marker_key in pro_visible

    def test_no_user_tier_drops_tier_gated_section(self) -> None:
        # When the caller doesn't know the user's tier, gated sections must not leak.
        marker_key = "_test_tier_gated_section"  # registered by the prior test if present
        if get_section(marker_key) is None:
            register_section(
                ContextSection(
                    key=marker_key,
                    display_name="Test gated",
                    description="ephemeral",
                    build=lambda _: "## Gated Marker\n- present",
                    requires_tier=SubscriptionTier.PRO,
                )
            )
        visible = [s.key for s in iter_effective_sections(enabled_keys=None, user_tier=None)]
        assert marker_key not in visible


class TestSectionInputsImmutability:
    def test_inputs_are_frozen(self) -> None:
        inputs = SectionInputs(signal={"symbol": "BTC"})
        with pytest.raises((AttributeError, TypeError)):
            inputs.signal = {"symbol": "ETH"}  # type: ignore[misc]


# =============================================================================
# str-or-enum boundary regression — pulsai.log AttributeError 2026-05-25 06:20:
#   File ".../rag_section_registry.py", line 103, in iter_effective
#   AttributeError: 'str' object has no attribute 'can_access'
#
# Root cause: ``UserModel.subscription_tier`` is ``Mapped[str]``, so when the
# ORM hydrates a user the value is a plain string ("free" / "pro" / ...).
# Downstream ``iter_effective`` typed ``user_tier`` as
# ``SubscriptionTier | None`` and called ``.can_access(...)`` on it →
# AttributeError on every ``/api/v1/ai/explain`` click for any user with
# tier-gated sections present.
#
# Fix: widen ``iter_effective`` to accept ``SubscriptionTier | str | None``
# and coerce via the SoT ``SubscriptionTier.coerce`` classmethod. This
# matches the existing widened signature on
# ``AIExplainConfigService.get_enabled_section_keys`` — both consumers of
# user_tier now accept either type, no caller is forced to coerce.
# =============================================================================


class TestIterEffectiveAcceptsStringUserTier:
    """Regression: ``iter_effective_sections`` must accept ORM-raw string tiers."""

    def test_string_user_tier_is_coerced_for_tier_gating(self) -> None:
        """The exact production failure path: ``user_tier="pro"`` → no crash.

        Without the fix this raised ``AttributeError: 'str' object has no
        attribute 'can_access'`` and 500'd the explain endpoint.
        """
        marker_key = "_test_tier_gated_section"
        if get_section(marker_key) is None:
            register_section(
                ContextSection(
                    key=marker_key,
                    display_name="Test gated",
                    description="ephemeral",
                    build=lambda _: "## Gated Marker\n- present",
                    requires_tier=SubscriptionTier.PRO,
                )
            )

        # Pass the RAW STRING value (what SQLAlchemy hands us).
        pro_visible = [s.key for s in iter_effective_sections(enabled_keys=None, user_tier="pro")]  # type: ignore[arg-type]
        free_visible = [s.key for s in iter_effective_sections(enabled_keys=None, user_tier="free")]  # type: ignore[arg-type]

        assert marker_key in pro_visible, "PRO string must access PRO-gated section"
        assert marker_key not in free_visible, "FREE string must NOT access PRO-gated section"

    def test_unknown_string_tier_is_treated_as_no_tier(self) -> None:
        """Defensive: an unparseable tier string must NOT crash; treats as no-tier."""
        marker_key = "_test_tier_gated_section"
        if get_section(marker_key) is None:
            register_section(
                ContextSection(
                    key=marker_key,
                    display_name="Test gated",
                    description="ephemeral",
                    build=lambda _: "## Gated Marker\n- present",
                    requires_tier=SubscriptionTier.PRO,
                )
            )

        # Garbage tier string — should not raise, gated section must be dropped.
        visible = [s.key for s in iter_effective_sections(enabled_keys=None, user_tier="not-a-tier")]  # type: ignore[arg-type]
        assert marker_key not in visible
