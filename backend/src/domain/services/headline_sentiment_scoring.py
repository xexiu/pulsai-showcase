"""
Pure headline / text sentiment aggregation (no ML imports).

Maps per-text FinBERT-style class probabilities to a compound score and summary stats.
SoT for formulas used by workers and tests; heavy inference lives in infrastructure.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# ProsusAI/finbert labels (lowercase from pipeline)
_POS_KEYS = frozenset({"positive", "pos", "label_0"})
_NEG_KEYS = frozenset({"negative", "neg", "label_1"})
_NEU_KEYS = frozenset({"neutral", "neu", "label_2"})

# SoT: minimum number of directional (non-neutral) headlines required to TRUST the
# directional signal — below this, one or two headlines are noise, so the neutral-
# inclusive mean is used instead. Shared by the display-value helper and the
# agent-breakdown conviction weight so both gate on the same volume.
MIN_DIRECTIONAL_VOLUME = 3


def _normalize_label_key(key: str) -> str | None:
    k = key.strip().lower()
    if k in _POS_KEYS or k.startswith("positive"):
        return "positive"
    if k in _NEG_KEYS or k.startswith("negative"):
        return "negative"
    if k in _NEU_KEYS or k.startswith("neutral"):
        return "neutral"
    return None


def dominant_label(row: Mapping[str, Any]) -> str | None:
    """Normalized argmax label (positive/negative/neutral) of a per-text score row.

    Used to split directional headlines from neutral ones: a headline whose
    highest-probability class is ``neutral`` carries no direction and is excluded
    from the directional aggregate (so a sea of neutrals can't drown a real signal).
    Public: also the SoT label for :func:`top_directional_drivers` (alert transparency),
    so a driver's label always agrees with the ``n_positive``/``n_negative`` counts.
    """
    best_label: str | None = None
    best_val = -1.0
    for raw_key, val in row.items():
        nk = _normalize_label_key(str(raw_key))
        if nk is None:
            continue
        fv = float(val)
        if fv > best_val:
            best_val = fv
            best_label = nk
    return best_label


def compound_from_class_probs(scores: Mapping[str, float]) -> float:
    """
    Map positive / negative / neutral probabilities to [-1, 1].

    compound = P(positive) - P(negative); neutral implicit in probs.
    """
    pos = 0.0
    neg = 0.0
    for raw_key, val in scores.items():
        nk = _normalize_label_key(str(raw_key))
        if nk == "positive":
            pos = max(pos, float(val))
        elif nk == "negative":
            neg = max(neg, float(val))
    return max(-1.0, min(1.0, pos - neg))


@dataclass(frozen=True, slots=True)
class HeadlineSentimentAggregate:
    """Aggregated headline sentiment over a batch of scored rows."""

    value: float
    """Normalized [-1, 1] weighted mean of per-text compounds (includes neutrals)."""
    n_texts: int
    pos_mean: float
    neg_mean: float
    neutral_mean: float
    directional_value: float = 0.0
    """Mean compound over ONLY directional (non-neutral-argmax) headlines, [-1, 1].

    The plain ``value`` is compressed toward 0 when most headlines are neutral
    (the common case); this isolates the signal carried by headlines the model
    actually called positive/negative. 0.0 when there are no directional rows.
    Unweighted by design — the optional per-source ``weights`` apply only to the
    neutral-inclusive ``value``; the directional signal weights every directional
    headline equally.
    """
    n_positive: int = 0
    n_negative: int = 0
    n_neutral: int = 0

    @property
    def directional_count(self) -> int:
        """Headlines with a positive/negative (non-neutral) dominant label."""
        return self.n_positive + self.n_negative


def aggregate_weighted_compounds(
    compounds: Sequence[float],
    weights: Sequence[float] | None = None,
) -> float:
    """Weighted average of compound scores; weights must match length if provided."""
    if not compounds:
        return 0.0
    n = len(compounds)
    if weights is None:
        return max(-1.0, min(1.0, sum(compounds) / n))
    if len(weights) != n:
        msg = "weights length must match compounds"
        raise ValueError(msg)
    total_w = sum(weights)
    if total_w <= 0:
        return max(-1.0, min(1.0, sum(compounds) / n))
    acc = sum(c * w for c, w in zip(compounds, weights, strict=True))
    return max(-1.0, min(1.0, acc / total_w))


def row_means(rows: Sequence[Mapping[str, Any]]) -> tuple[float, float, float]:
    """Mean positive, negative, neutral probabilities across rows (missing = 0)."""
    if not rows:
        return 0.0, 0.0, 0.0

    def pick(row: Mapping[str, Any], label: str) -> float:
        for k, v in row.items():
            if _normalize_label_key(str(k)) == label:
                return float(v)
        return 0.0

    n = len(rows)
    pos = sum(pick(r, "positive") for r in rows) / n
    neg = sum(pick(r, "negative") for r in rows) / n
    neu = sum(pick(r, "neutral") for r in rows) / n
    return pos, neg, neu


def aggregate_headline_rows(
    rows: Sequence[Mapping[str, Any]],
    weights: Sequence[float] | None = None,
) -> HeadlineSentimentAggregate:
    """
    Build aggregate from per-text score dicts (e.g. {\"positive\": 0.7, \"negative\": 0.2}).
    """
    if not rows:
        return HeadlineSentimentAggregate(
            value=0.0,
            n_texts=0,
            pos_mean=0.0,
            neg_mean=0.0,
            neutral_mean=0.0,
        )

    compounds = [compound_from_class_probs(r) for r in rows]
    value = aggregate_weighted_compounds(compounds, weights)
    pos_m, neg_m, neu_m = row_means(rows)

    labels = [dominant_label(r) for r in rows]
    n_positive = sum(1 for lbl in labels if lbl == "positive")
    n_negative = sum(1 for lbl in labels if lbl == "negative")
    n_neutral = sum(1 for lbl in labels if lbl == "neutral")
    directional = [c for c, lbl in zip(compounds, labels, strict=True) if lbl in ("positive", "negative")]
    directional_value = max(-1.0, min(1.0, sum(directional) / len(directional))) if directional else 0.0

    return HeadlineSentimentAggregate(
        value=value,
        n_texts=len(rows),
        pos_mean=pos_m,
        neg_mean=neg_m,
        neutral_mean=neu_m,
        directional_value=directional_value,
        n_positive=n_positive,
        n_negative=n_negative,
        n_neutral=n_neutral,
    )


def effective_sentiment_value(agg: HeadlineSentimentAggregate) -> float:
    """Card/aggregate-facing value: directional signal when trustworthy, else the mean.

    Uses the directional (neutral-excluded) value once there are at least
    ``MIN_DIRECTIONAL_VOLUME`` directional headlines — so a genuine pump/dump is
    surfaced instead of being compressed toward 0 by a sea of neutrals — and
    falls back to the neutral-inclusive mean (≈0 / NEUTRAL) when the directional
    sample is too small to trust.
    """
    if agg.directional_count >= MIN_DIRECTIONAL_VOLUME:
        return agg.directional_value
    return agg.value


@dataclass(frozen=True, slots=True)
class HeadlineDriver:
    """One DIRECTIONAL headline that contributed to a blended sentiment value.

    Alert-transparency primitive (Telegram "top drivers" section): a human judging a
    high-conviction alert needs to see WHICH headlines moved the score, not just the
    aggregate counts.
    """

    text: str
    source: str
    score: float
    """Compound sentiment score in [-1, 1] (see :func:`compound_from_class_probs`)."""
    label: str
    """``"positive"`` or ``"negative"`` — never ``"neutral"`` (excluded, see below)."""


_UNKNOWN_HEADLINE_SOURCE = "unknown"


def top_directional_drivers(
    texts: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    source_by_text: Mapping[str, str],
    *,
    limit: int,
    lead_positive: bool | None = None,
) -> list[HeadlineDriver]:
    """Top ``limit`` directional headlines, BALANCED across bullish and bearish.

    Pure; no I/O. ``texts`` and ``rows`` must align 1:1 (same contract as
    :func:`aggregate_headline_rows` given ``rows``) — each row is the per-text FinBERT-style
    class-probability dict for the text at the same index. Neutral-dominant headlines carry no
    directional signal and are excluded, mirroring ``directional_count`` elsewhere in this
    module. ``source_by_text`` is a best-effort text -> display-source lookup (e.g. RSS feed
    name); a text missing from it renders as ``"unknown"`` rather than raising.

    Args:
        texts: Headline texts, freshest-first (same order used to build ``rows``).
        rows: Per-text class-probability dicts, aligned 1:1 with ``texts``.
        source_by_text: Headline text -> source display name (e.g. RSS feed name).
        limit: Maximum number of drivers to return, SPLIT between the two directions.
        lead_positive: The verdict's own direction, so a bullish alert opens with what made it
            bullish and shows the bearish counterweight after. ``None`` orders strongest-first.

    Returns:
        Up to ``limit`` :class:`HeadlineDriver`, each side ranked by ``|score|`` descending.
    """
    drivers: list[HeadlineDriver] = []
    for text, row in zip(texts, rows, strict=True):
        label = dominant_label(row)
        if label is None or label == "neutral":
            continue
        drivers.append(
            HeadlineDriver(
                text=text,
                source=source_by_text.get(text, _UNKNOWN_HEADLINE_SOURCE),
                score=compound_from_class_probs(row),
                label=label,
            )
        )
    return _balance_drivers(drivers, limit=limit, lead_positive=lead_positive)


def _balance_drivers(
    drivers: list[HeadlineDriver],
    *,
    limit: int,
    lead_positive: bool | None,
) -> list[HeadlineDriver]:
    """Split the budget between bullish and bearish, each side ranked by ``|score|``.

    A single ``abs(score)`` ranking over the whole pool is what produced 141 of 141 bullish alerts
    explained entirely by bearish headlines: FinBERT's negative class saturates harder on financial
    copy (measured mean ``|score|`` 0.9602 bearish vs 0.9333 bullish over 1,716 real driver slots),
    so the bearish tail takes every slot — 22 of 1,716 ever went to a bullish headline.

    Each side keeps its own magnitude ranking, so balancing costs no strength: the strongest
    bullish and the strongest bearish headline are what appear.

    An ODD ``limit`` cannot split evenly. The spare slot goes to the side holding the single
    hardest headline — the same tie-break the old ranking used, so the strongest signal stays on
    screen.

    A genuinely one-sided news day BACKFILLS to ``limit`` from whichever side has headlines.
    Padding a real all-bearish day down to half the budget would trade one misleading display for
    another.
    """
    if limit <= 0 or not drivers:
        return []

    positives = sorted((d for d in drivers if d.score > 0), key=lambda d: abs(d.score), reverse=True)
    negatives = sorted((d for d in drivers if d.score < 0), key=lambda d: abs(d.score), reverse=True)

    # Derived from `limit` — never a second constant that has to be kept in step with the first.
    half = limit // 2
    spare = limit - 2 * half
    pos_budget, neg_budget = half, half
    if spare:
        strongest_is_positive = bool(positives) and (not negatives or abs(positives[0].score) >= abs(negatives[0].score))
        if strongest_is_positive:
            pos_budget += spare
        else:
            neg_budget += spare

    picked_pos = positives[:pos_budget]
    picked_neg = negatives[:neg_budget]

    # Backfill: an unused slot on one side goes to the other rather than shrinking the section.
    shortfall = limit - len(picked_pos) - len(picked_neg)
    if shortfall > 0:
        picked_pos += positives[len(picked_pos) : len(picked_pos) + shortfall]
        shortfall = limit - len(picked_pos) - len(picked_neg)
    if shortfall > 0:
        picked_neg += negatives[len(picked_neg) : len(picked_neg) + shortfall]

    # `lead_positive` is the VERDICT's direction: a bullish alert opens with what made it bullish,
    # then shows the counterweight. Without it, fall back to strongest-first.
    if lead_positive is None:
        return sorted([*picked_pos, *picked_neg], key=lambda d: abs(d.score), reverse=True)
    return [*picked_pos, *picked_neg] if lead_positive else [*picked_neg, *picked_pos]
