"""Behavior tests for LLM news-impact parsing, aggregation, and the FinBERT blend.

The blend is the heart of Phase 2: it lets a confident macro verdict (which
FinBERT misses) move a news card that FinBERT scored NEUTRAL, while staying a
conviction-weighted average (no hard override) and reducing EXACTLY to Phase-1
behavior when the LLM is absent or neutral.
"""

from __future__ import annotations

import pytest

from src.domain.services.news_impact_scoring import (
    NewsImpactAggregate,
    NewsImpactLabel,
    NewsImpactVerdict,
    aggregate_impact_verdicts,
    blend_news_signal,
    parse_impact_verdict,
    signed_impact_value,
)

# ── parse ────────────────────────────────────────────────────────────────────


def test_parse_strict_format() -> None:
    v = parse_impact_verdict("VERDICT=BULLISH | CONF=0.80")
    assert v == NewsImpactVerdict(label=NewsImpactLabel.BULLISH, confidence=0.80)


def test_parse_is_case_and_whitespace_tolerant() -> None:
    v = parse_impact_verdict("  verdict = bearish  |  conf = 0.6 \n")
    assert v is not None
    assert v.label is NewsImpactLabel.BEARISH
    assert v.confidence == pytest.approx(0.6)


def test_parse_neutral_without_confidence_defaults_to_zero_conf() -> None:
    v = parse_impact_verdict("VERDICT=NEUTRAL")
    assert v is not None
    assert v.label is NewsImpactLabel.NEUTRAL
    assert v.confidence == 0.0


def test_parse_tolerates_trailing_model_chatter() -> None:
    v = parse_impact_verdict("VERDICT=BULLISH | CONF=0.91 | WHY=ceasefire risk-on")
    assert v is not None
    assert v.label is NewsImpactLabel.BULLISH
    assert v.confidence == pytest.approx(0.91)


def test_parse_unparseable_returns_none() -> None:
    assert parse_impact_verdict("I cannot determine the impact of this headline.") is None
    assert parse_impact_verdict("") is None


def test_parse_directional_without_confidence_is_rejected() -> None:
    # A directional call with no confidence is untrustworthy → drop it (unlike NEUTRAL).
    assert parse_impact_verdict("VERDICT=BULLISH") is None


def test_parse_clamps_confidence_to_unit_range() -> None:
    assert parse_impact_verdict("VERDICT=BULLISH | CONF=1.5").confidence == 1.0  # type: ignore[union-attr]


# ── signed value (confidence gate) ────────────────────────────────────────────


def test_signed_value_signs_by_direction() -> None:
    assert signed_impact_value(NewsImpactVerdict(NewsImpactLabel.BULLISH, 0.8)) == pytest.approx(0.8)
    assert signed_impact_value(NewsImpactVerdict(NewsImpactLabel.BEARISH, 0.8)) == pytest.approx(-0.8)
    assert signed_impact_value(NewsImpactVerdict(NewsImpactLabel.NEUTRAL, 0.9)) == 0.0


def test_low_confidence_directional_verdict_is_neutralised() -> None:
    # A hedging "BULLISH conf=0.3" carries no actionable signal.
    assert signed_impact_value(NewsImpactVerdict(NewsImpactLabel.BULLISH, 0.30)) == 0.0


# ── aggregate ─────────────────────────────────────────────────────────────────


def test_aggregate_means_over_directional_only() -> None:
    verdicts = [
        NewsImpactVerdict(NewsImpactLabel.BULLISH, 0.9),
        NewsImpactVerdict(NewsImpactLabel.BULLISH, 0.7),
        NewsImpactVerdict(NewsImpactLabel.NEUTRAL, 0.0),  # excluded from the mean
    ]
    agg = aggregate_impact_verdicts(verdicts)
    assert agg.value == pytest.approx(0.8)
    assert agg.n_directional == 2
    assert agg.n_classified == 3


def test_aggregate_all_neutral_or_low_conf_is_zero_signal() -> None:
    agg = aggregate_impact_verdicts(
        [
            NewsImpactVerdict(NewsImpactLabel.NEUTRAL, 0.0),
            NewsImpactVerdict(NewsImpactLabel.BULLISH, 0.2),  # below gate → neutral
        ]
    )
    assert agg.value == 0.0
    assert agg.n_directional == 0
    assert agg.n_classified == 2


def test_aggregate_ignores_failed_none_verdicts_in_classified_count() -> None:
    agg = aggregate_impact_verdicts([NewsImpactVerdict(NewsImpactLabel.BEARISH, 0.8), None])
    assert agg.value == pytest.approx(-0.8)
    assert agg.n_directional == 1
    assert agg.n_classified == 1


def test_aggregate_empty_is_zero() -> None:
    agg = aggregate_impact_verdicts([])
    assert agg == NewsImpactAggregate(value=0.0, n_directional=0, n_classified=0)


def test_aggregate_lead_value_is_freshest_directional_verdict() -> None:
    """Lead macro = first directional verdict in freshness order (not batch mean)."""
    verdicts = [
        NewsImpactVerdict(NewsImpactLabel.BULLISH, 0.75),
        NewsImpactVerdict(NewsImpactLabel.BEARISH, 0.70),
        NewsImpactVerdict(NewsImpactLabel.BEARISH, 0.75),
    ]
    agg = aggregate_impact_verdicts(verdicts)
    assert agg.lead_value == pytest.approx(0.75)
    assert agg.value == pytest.approx((0.75 - 0.70 - 0.75) / 3)


def test_aggregate_lead_skips_neutral_and_low_confidence_prefix() -> None:
    verdicts = [
        NewsImpactVerdict(NewsImpactLabel.NEUTRAL, 0.0),
        NewsImpactVerdict(NewsImpactLabel.BULLISH, 0.30),  # below gate
        NewsImpactVerdict(NewsImpactLabel.BEARISH, 0.80),
    ]
    agg = aggregate_impact_verdicts(verdicts)
    assert agg.lead_value == pytest.approx(-0.80)


# ── blend ─────────────────────────────────────────────────────────────────────


def test_blend_without_llm_reduces_to_finbert_effective_value() -> None:
    # Phase-1 behavior preserved exactly when the LLM is absent.
    out = blend_news_signal(finbert_effective_value=0.42, finbert_directional_count=5, impact=None)
    assert out.value == pytest.approx(0.42)
    assert out.blend_source == "finbert"


def test_blend_neutral_finbert_plus_confident_macro_flips_the_card() -> None:
    # The user's exact bug: FinBERT NEUTRAL on a ceasefire, LLM says BULLISH.
    impact = NewsImpactAggregate(value=0.85, n_directional=1, n_classified=1)
    out = blend_news_signal(finbert_effective_value=0.0, finbert_directional_count=0, impact=impact)
    assert out.value == pytest.approx(0.85)
    assert out.blend_source == "llm"
    assert out.llm_value == pytest.approx(0.85)
    assert out.llm_n_directional == 1


def test_blend_combines_when_both_have_directional_signal() -> None:
    impact = NewsImpactAggregate(value=0.8, n_directional=1, n_classified=1)
    out = blend_news_signal(finbert_effective_value=0.1, finbert_directional_count=5, impact=impact)
    # conviction-weighted average lands strictly between the two inputs.
    assert 0.1 < out.value < 0.8
    assert out.blend_source == "blended"


def test_blend_neutral_llm_keeps_finbert() -> None:
    impact = NewsImpactAggregate(value=0.0, n_directional=0, n_classified=3)
    out = blend_news_signal(finbert_effective_value=0.3, finbert_directional_count=4, impact=impact)
    assert out.value == pytest.approx(0.3)
    assert out.blend_source == "finbert"


def test_blend_no_directional_signal_anywhere_keeps_finbert_value() -> None:
    # impact present but all-neutral AND FinBERT has no directional headlines:
    # total weight is 0 → fall back to the (neutral) FinBERT value, source finbert.
    impact = NewsImpactAggregate(value=0.0, n_directional=0, n_classified=4)
    out = blend_news_signal(finbert_effective_value=0.0, finbert_directional_count=0, impact=impact)
    assert out.value == 0.0
    assert out.blend_source == "finbert"


def test_blend_clamps_to_unit_range() -> None:
    impact = NewsImpactAggregate(value=1.0, n_directional=3, n_classified=3)
    out = blend_news_signal(finbert_effective_value=1.0, finbert_directional_count=8, impact=impact)
    assert -1.0 <= out.value <= 1.0


def test_blend_flags_conflict_on_opposite_directions() -> None:
    # Bullish crypto tone vs a bearish macro verdict — surfaced, not silently averaged.
    impact = NewsImpactAggregate(value=-0.9, n_directional=1, n_classified=1)
    out = blend_news_signal(finbert_effective_value=0.4, finbert_directional_count=4, impact=impact)
    assert out.conflict is True


def test_blend_no_conflict_when_aligned() -> None:
    impact = NewsImpactAggregate(value=0.8, n_directional=1, n_classified=1)
    out = blend_news_signal(finbert_effective_value=0.4, finbert_directional_count=4, impact=impact)
    assert out.conflict is False


def test_blend_no_conflict_without_llm() -> None:
    out = blend_news_signal(finbert_effective_value=0.5, finbert_directional_count=5, impact=None)
    assert out.conflict is False


def test_blend_warsh_lead_bullish_prevails_over_stale_bearish_finbert() -> None:
    """Regression (2026-07-01 Sintra): freshest macro BULLISH must reach FE BUY (>0.2)."""
    impact = NewsImpactAggregate(
        value=-0.338,
        n_directional=4,
        n_classified=11,
        lead_value=0.75,
    )
    out = blend_news_signal(
        finbert_effective_value=-0.2822,
        finbert_directional_count=21,
        impact=impact,
    )
    assert out.value >= 0.2
    assert out.lead_dominant is True
    assert out.conflict is True


def test_blend_lead_dominant_uses_lead_not_stale_batch_mean() -> None:
    impact = NewsImpactAggregate(
        value=-0.42,
        n_directional=5,
        n_classified=12,
        lead_value=0.85,
    )
    out = blend_news_signal(
        finbert_effective_value=-0.15,
        finbert_directional_count=10,
        impact=impact,
    )
    assert out.value >= 0.2
    assert out.llm_value == pytest.approx(0.85)
