"""LLM news-impact verdicts: parsing, aggregation, and the FinBERT blend (pure).

Phase 2 heart. An LLM impact pass returns a one-line verdict per macro headline;
this module parses it, aggregates a batch into a single [-1, 1] signal, and blends
that with FinBERT's directional value so a confident macro verdict (FinBERT's
blind spot) can move a card FinBERT scored NEUTRAL — WITHOUT a hard override.

The blend is a conviction-weighted average and reduces EXACTLY to Phase-1
behavior (``effective_sentiment_value``) when the LLM is absent or neutral, so
the worker / endpoint path is unchanged when no provider is configured.

No I/O, no model imports — heavy inference lives in infrastructure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

from src.domain.services.headline_sentiment_scoring import MIN_DIRECTIONAL_VOLUME
from src.shared.constants.news_impact import (
    NEWS_IMPACT_CONFLICT_DEADBAND,
    NEWS_IMPACT_FINBERT_WEIGHT_CAP,
    NEWS_IMPACT_FINBERT_WEIGHT_CAP_ON_LEAD,
    NEWS_IMPACT_LEAD_VERDICT_WEIGHT,
    NEWS_IMPACT_LLM_PER_VERDICT_WEIGHT,
    NEWS_IMPACT_MIN_CONFIDENCE,
)


class NewsImpactLabel(StrEnum):
    """Directional impact label the LLM emits for a headline."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class NewsImpactVerdict:
    """One headline's parsed LLM verdict."""

    label: NewsImpactLabel
    confidence: float
    """[0, 1] model confidence; below ``NEWS_IMPACT_MIN_CONFIDENCE`` it is treated as no signal."""


@dataclass(frozen=True, slots=True)
class NewsImpactAggregate:
    """Aggregate LLM impact over a batch of macro headlines."""

    value: float
    """Mean signed confidence over DIRECTIONAL (non-neutral, above-gate) verdicts, [-1, 1]."""
    n_directional: int
    n_classified: int
    """Verdicts successfully parsed (excludes failed / unparseable LLM calls)."""
    lead_value: float = 0.0
    """Signed value of the FRESHEST directional macro verdict (input order), else 0."""
    n_macro_total: int = 0
    """Macro-routed headlines in the batch before the per-cycle LLM cap."""
    n_macro_dropped: int = 0
    """Macro headlines dropped because they exceeded ``NEWS_IMPACT_MAX_HEADLINES_PER_CYCLE``."""

    @property
    def lead_directional(self) -> bool:
        """True when the freshest macro headline carried an actionable directional verdict."""
        return self.lead_value != 0.0


BlendSource = Literal["finbert", "llm", "blended"]


@dataclass(frozen=True, slots=True)
class BlendedNewsSignal:
    """FinBERT + LLM blended news signal for the snapshot card."""

    value: float
    blend_source: BlendSource
    llm_value: float
    llm_n_directional: int
    conflict: bool = False
    """FinBERT and the LLM macro verdict point in OPPOSITE directions (both directional)."""
    lead_dominant: bool = False
    """Freshest macro LLM verdict drove the blend (DeepSeek prevails over FinBERT tone)."""
    finbert_baseline: float = 0.0
    """FinBERT centring actually applied (0.0 = uncentred), so the snapshot records how the card was built."""


_VERDICT_RE = re.compile(r"VERDICT\s*=\s*(BULLISH|BEARISH|NEUTRAL)", re.IGNORECASE)
_CONF_RE = re.compile(r"CONF\s*=\s*([01](?:\.\d+)?)", re.IGNORECASE)


def _clamp_unit(value: float) -> float:
    return max(-1.0, min(1.0, value))


def parse_impact_verdict(text: str) -> NewsImpactVerdict | None:
    """Parse a ``VERDICT=<dir> | CONF=<0..1>`` line; ``None`` if no verdict found.

    Tolerant of case, surrounding whitespace, and trailing model chatter. A
    directional verdict with no parseable confidence is rejected (None); a NEUTRAL
    verdict defaults to 0.0 confidence (it carries no signal regardless).
    """
    if not text:
        return None
    verdict_match = _VERDICT_RE.search(text)
    if verdict_match is None:
        return None
    label = NewsImpactLabel(verdict_match.group(1).upper())
    conf_match = _CONF_RE.search(text)
    if conf_match is None:
        if label is NewsImpactLabel.NEUTRAL:
            return NewsImpactVerdict(label=label, confidence=0.0)
        return None
    confidence = max(0.0, min(1.0, float(conf_match.group(1))))
    return NewsImpactVerdict(label=label, confidence=confidence)


def signed_impact_value(verdict: NewsImpactVerdict) -> float:
    """Signed [-1, 1] value: +conf BULLISH, -conf BEARISH, 0 NEUTRAL or below the gate."""
    if verdict.label is NewsImpactLabel.NEUTRAL:
        return 0.0
    if verdict.confidence < NEWS_IMPACT_MIN_CONFIDENCE:
        return 0.0
    sign = 1.0 if verdict.label is NewsImpactLabel.BULLISH else -1.0
    return sign * verdict.confidence


def aggregate_impact_verdicts(verdicts: list[NewsImpactVerdict | None]) -> NewsImpactAggregate:
    """Reduce per-headline verdicts to one signal (mean over directional only).

    ``None`` entries are failed / unparseable LLM calls and are excluded from BOTH
    the mean and ``n_classified``. The mean excludes neutral / below-gate verdicts
    so a decisive macro verdict is not diluted by ``no-impact`` ones — mirrors
    FinBERT's neutral-excluded ``directional_value``.
    """
    parsed = [v for v in verdicts if v is not None]
    directional: list[float] = []
    lead_value = 0.0
    for signed in (signed_impact_value(v) for v in parsed):
        if signed == 0.0:
            continue
        directional.append(signed)
        if lead_value == 0.0:
            lead_value = signed
    value = sum(directional) / len(directional) if directional else 0.0
    return NewsImpactAggregate(
        value=_clamp_unit(value),
        n_directional=len(directional),
        n_classified=len(parsed),
        lead_value=_clamp_unit(lead_value),
    )


def blend_news_signal(
    *,
    finbert_effective_value: float,
    finbert_directional_count: int,
    impact: NewsImpactAggregate | None,
    finbert_baseline: float = 0.0,
) -> BlendedNewsSignal:
    """Conviction-weighted blend of FinBERT's effective value and the LLM impact.

    ``finbert_effective_value`` is the Phase-1 card value (``effective_sentiment_value``).
    Weights: FinBERT ∝ its directional headline count (capped), LLM ∝ its directional
    verdict count. With no LLM signal the result is exactly ``finbert_effective_value``
    (Phase-1 preserved); with FinBERT neutral and a confident macro verdict, the LLM
    dominates and the card flips.

    ``finbert_baseline`` centres FinBERT before it enters the blend or the conflict check.
    Measured 2026-09-11 on 9,709 snapshots: FinBERT's effective tone is negative 89.5% of the
    time (median -0.2305), which turned the LLM's 2.84:1 bearish lean into 9.8:1 at the 0.6
    alert gate (2.5:1 once centred). The default 0.0 reproduces the previous behaviour exactly.
    It applies only when FinBERT has ``MIN_DIRECTIONAL_VOLUME`` directional headlines: below that
    the effective value is the neutral-inclusive mean (0.0 for an empty feed), a different quantity
    from the directional tone the baseline measures, and centring it would make an empty feed bullish.
    """
    applied_baseline = finbert_baseline if finbert_directional_count >= MIN_DIRECTIONAL_VOLUME else 0.0
    finbert_value = finbert_effective_value - applied_baseline
    if impact is None:
        return BlendedNewsSignal(
            value=_clamp_unit(finbert_value),
            blend_source="finbert",
            llm_value=0.0,
            llm_n_directional=0,
            finbert_baseline=applied_baseline,
        )

    lead_dominant = impact.lead_directional
    if lead_dominant:
        llm_signal = impact.lead_value
        llm_weight = NEWS_IMPACT_LEAD_VERDICT_WEIGHT
        fb_weight = float(min(max(finbert_directional_count, 0), NEWS_IMPACT_FINBERT_WEIGHT_CAP_ON_LEAD))
        conflict = abs(finbert_value) > NEWS_IMPACT_CONFLICT_DEADBAND and (finbert_value > 0) != (llm_signal > 0)
    else:
        llm_signal = impact.value
        fb_weight = float(min(max(finbert_directional_count, 0), NEWS_IMPACT_FINBERT_WEIGHT_CAP))
        llm_weight = impact.n_directional * NEWS_IMPACT_LLM_PER_VERDICT_WEIGHT
        conflict = (
            abs(finbert_value) > NEWS_IMPACT_CONFLICT_DEADBAND
            and abs(impact.value) > NEWS_IMPACT_CONFLICT_DEADBAND
            and (finbert_value > 0) != (impact.value > 0)
        )

    # finbert_effective_value already encodes the MIN_DIRECTIONAL_VOLUME trust gate
    total_weight = fb_weight + llm_weight

    if total_weight <= 0:
        value = finbert_value
        source: BlendSource = "finbert"
    else:
        value = (finbert_value * fb_weight + llm_signal * llm_weight) / total_weight
        if fb_weight > 0 and llm_weight > 0:
            source = "blended"
        elif llm_weight > 0:
            source = "llm"
        else:
            source = "finbert"

    return BlendedNewsSignal(
        value=_clamp_unit(value),
        blend_source=source,
        llm_value=llm_signal,
        llm_n_directional=impact.n_directional if not lead_dominant else 1,
        conflict=conflict,
        lead_dominant=lead_dominant,
        finbert_baseline=applied_baseline,
    )


@dataclass(frozen=True, slots=True)
class FinbertBaseline:
    """The FinBERT centring to apply and the size of the trailing sample it was read from.

    One value because the two always travel together: the snapshot records both, and a bare float would
    lose the sample size that says WHY a baseline is 0.0 (no history yet, rather than a neutral tone).
    """

    value: float = 0.0
    sample_n: int = 0


UNCENTRED_FINBERT_BASELINE: Final[FinbertBaseline] = FinbertBaseline()


def finbert_centring_baseline(sample_median: float | None, sample_count: int, *, min_samples: int) -> FinbertBaseline:
    """The FinBERT baseline to centre the blend on: the trailing median once its sample is trusted, else 0.0.

    ``sample_median`` / ``sample_count`` describe persisted ``finbert_effective_value`` over the trailing
    window. A value of 0.0 reproduces the uncentred blend exactly, so a cold start, a history outage, or a
    window that still holds only a few rows (one news regime) degrades to the previous behaviour instead of
    centring on it. The sample size is kept either way, so the snapshot shows how close centring is.
    """
    if sample_median is None or sample_count < min_samples:
        return FinbertBaseline(value=0.0, sample_n=sample_count)
    return FinbertBaseline(value=sample_median, sample_n=sample_count)
