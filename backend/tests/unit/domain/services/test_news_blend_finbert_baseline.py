"""FinBERT centring in the news blend (NEWS-3, 2026-09-11).

MEASURED on 9,709 prod snapshots: FinBERT's effective tone is negative 89.5% of the time (median
-0.2305). With the lead verdict weighted 8 and FinBERT 2, that constant pull turned the LLM's
2.84:1 bearish lean into a 9.8:1 bearish lean at the 0.6 alert gate; centring FinBERT on its
median gives 2.5:1. The gate skew was FinBERT tone bias, not lead dominance, so lead dominance
stays (pinned by the lead tests in test_news_impact_scoring.py).

Changed the same day: finbert_centring_baseline returned a bare float. That did not hold because
ruff PLR0913 (max 8 arguments) refused the snapshot builder once it had to take the value AND its
sample size as two parameters; the two always travel together, so the function now returns one
FinbertBaseline. No rule changed: same trust threshold, same directional-volume guard.

REUSE-AUDIT: considered tests/unit/domain/services/test_news_impact_scoring.py — it pins parsing,
aggregation and the existing blend; not extending it because these tests pin one new input (the
baseline) and its symmetry property, which reads more clearly as its own contract.
"""

from __future__ import annotations

import pytest

from src.domain.services.headline_sentiment_scoring import MIN_DIRECTIONAL_VOLUME
from src.domain.services.news_impact_scoring import (
    UNCENTRED_FINBERT_BASELINE,
    FinbertBaseline,
    NewsImpactAggregate,
    blend_news_signal,
    finbert_centring_baseline,
)
from src.infrastructure.config.settings import settings

_FINBERT_MEDIAN_MEASURED = -0.2305
_DIRECTIONAL_COUNT = 40
_ONE_DAY_OF_REFRESHES = 288


def _lead(value: float) -> NewsImpactAggregate:
    return NewsImpactAggregate(value=value, n_directional=1, n_classified=1, lead_value=value)


def test_a_zero_baseline_leaves_the_blend_exactly_as_before() -> None:
    before = blend_news_signal(finbert_effective_value=-0.2, finbert_directional_count=_DIRECTIONAL_COUNT, impact=_lead(0.75))
    same = blend_news_signal(finbert_effective_value=-0.2, finbert_directional_count=_DIRECTIONAL_COUNT, impact=_lead(0.75), finbert_baseline=0.0)

    assert same == before


def test_the_2026_09_11_bullish_flip_clears_the_alert_gate_once_finbert_is_centred() -> None:
    """THE INCIDENT: at 12:50 UTC a +0.75 lead with FinBERT at -0.1815 blended to +0.5637 and missed 0.6."""
    uncentred = blend_news_signal(finbert_effective_value=-0.1815, finbert_directional_count=59, impact=_lead(0.75))
    centred = blend_news_signal(
        finbert_effective_value=-0.1815, finbert_directional_count=59, impact=_lead(0.75), finbert_baseline=_FINBERT_MEDIAN_MEASURED
    )

    assert uncentred.value == pytest.approx(0.5637, abs=1e-4)
    assert uncentred.value < settings.news_sentiment_tg_alert_min_abs_value
    assert centred.value >= settings.news_sentiment_tg_alert_min_abs_value


def test_centring_makes_the_blend_symmetric_in_the_lead_direction() -> None:
    bull = blend_news_signal(
        finbert_effective_value=_FINBERT_MEDIAN_MEASURED,
        finbert_directional_count=_DIRECTIONAL_COUNT,
        impact=_lead(0.75),
        finbert_baseline=_FINBERT_MEDIAN_MEASURED,
    )
    bear = blend_news_signal(
        finbert_effective_value=_FINBERT_MEDIAN_MEASURED,
        finbert_directional_count=_DIRECTIONAL_COUNT,
        impact=_lead(-0.75),
        finbert_baseline=_FINBERT_MEDIAN_MEASURED,
    )

    assert bull.value == pytest.approx(-bear.value)


def test_conflict_is_judged_on_the_centred_finbert_value() -> None:
    """FinBERT sitting at its own median is not bearish news and must not flag a conflict."""
    uncentred = blend_news_signal(finbert_effective_value=_FINBERT_MEDIAN_MEASURED, finbert_directional_count=_DIRECTIONAL_COUNT, impact=_lead(0.75))
    centred = blend_news_signal(
        finbert_effective_value=_FINBERT_MEDIAN_MEASURED,
        finbert_directional_count=_DIRECTIONAL_COUNT,
        impact=_lead(0.75),
        finbert_baseline=_FINBERT_MEDIAN_MEASURED,
    )

    assert uncentred.conflict is True
    assert centred.conflict is False


def test_without_an_llm_verdict_the_card_is_the_centred_finbert_value() -> None:
    result = blend_news_signal(
        finbert_effective_value=-0.1815, finbert_directional_count=_DIRECTIONAL_COUNT, impact=None, finbert_baseline=_FINBERT_MEDIAN_MEASURED
    )

    assert result.value == pytest.approx(-0.1815 - _FINBERT_MEDIAN_MEASURED)
    assert result.blend_source == "finbert"


def test_a_snapshot_without_finbert_directional_volume_is_not_centred() -> None:
    """An empty feed must not read bullish.

    The baseline is FinBERT's DIRECTIONAL tone. Below MIN_DIRECTIONAL_VOLUME the effective value is
    the neutral-inclusive mean (0.0 with no headlines at all), a different quantity, so centring it
    would turn a feed outage into a +0.23 bullish card.
    """
    empty = blend_news_signal(finbert_effective_value=0.0, finbert_directional_count=0, impact=None, finbert_baseline=_FINBERT_MEDIAN_MEASURED)
    thin = blend_news_signal(
        finbert_effective_value=-0.05,
        finbert_directional_count=MIN_DIRECTIONAL_VOLUME - 1,
        impact=None,
        finbert_baseline=_FINBERT_MEDIAN_MEASURED,
    )

    assert empty.value == 0.0
    assert empty.finbert_baseline == 0.0
    assert thin.value == pytest.approx(-0.05)


def test_the_baseline_is_the_trailing_median_only_once_the_sample_is_trusted() -> None:
    trusted = finbert_centring_baseline(-0.25, _ONE_DAY_OF_REFRESHES, min_samples=_ONE_DAY_OF_REFRESHES)
    untrusted = finbert_centring_baseline(-0.25, _ONE_DAY_OF_REFRESHES - 1, min_samples=_ONE_DAY_OF_REFRESHES)

    assert trusted == FinbertBaseline(value=-0.25, sample_n=_ONE_DAY_OF_REFRESHES)
    assert untrusted == FinbertBaseline(value=0.0, sample_n=_ONE_DAY_OF_REFRESHES - 1), "the sample size is kept: it says how close centring is"


def test_no_history_means_no_centring() -> None:
    """Cold start, a history outage, or only rows written before the value was persisted: behave as before."""
    assert finbert_centring_baseline(None, 0, min_samples=_ONE_DAY_OF_REFRESHES) == UNCENTRED_FINBERT_BASELINE
