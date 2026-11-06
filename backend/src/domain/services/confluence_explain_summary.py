"""Multi-timeframe confluence summary for the AI explainer (pure domain).

Describes the co-temporal set of signals on one symbol across timeframes so the
explainer can narrate the COMBINED picture. Unlike the worker's
``detect_confluence`` (which returns ``None`` unless an agreeing majority is worth
a Telegram push), this ALWAYS summarizes — including disagreement — because the
explanation must surface a conflicted picture rather than hide it. Kept separate
from ``detect_confluence`` on purpose: different consumer, different semantics
(notify-on-agreement vs explain-the-whole-set).

No I/O. Legs are ordered by ``ALIGNMENT_TIMEFRAMES_ORDER`` so the narrative reads
shortest→longest timeframe.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from src.domain.enums import SignalAction
from src.shared.constants.timeframes import ALIGNMENT_TIMEFRAMES_ORDER

DominantAction = Literal["BUY", "SELL", "HOLD", "MIXED"]
_MIXED: DominantAction = "MIXED"


@dataclass(frozen=True, slots=True)
class ConfluenceLeg:
    """One timeframe's signal in the confluence set."""

    timeframe: str
    action: str  # SignalAction value: BUY / SELL / HOLD
    confidence: float


@dataclass(frozen=True, slots=True)
class ConfluenceExplainSummary:
    """Combined directional picture across the co-temporal legs."""

    symbol: str
    legs: tuple[ConfluenceLeg, ...]
    """Legs ordered shortest→longest timeframe (ALIGNMENT_TIMEFRAMES_ORDER)."""
    dominant_action: DominantAction
    agreeing_count: int
    """Legs voting the lead action (the larger of BUY/SELL when MIXED)."""
    total: int
    mean_confidence: float
    """Mean confidence over the agreeing legs (0.0 when there are none)."""
    is_unanimous: bool
    is_conflicted: bool
    """At least one BUY AND one SELL leg — a directional clash the explainer must flag."""


def _tf_sort_key(timeframe: str) -> int:
    """Index in ALIGNMENT_TIMEFRAMES_ORDER; unknown timeframes sort last."""
    try:
        return ALIGNMENT_TIMEFRAMES_ORDER.index(timeframe)
    except ValueError:
        return len(ALIGNMENT_TIMEFRAMES_ORDER)


def summarize_confluence(symbol: str, legs: Sequence[ConfluenceLeg]) -> ConfluenceExplainSummary:
    """Summarize the co-temporal legs into one directional picture (always returns)."""
    ordered = tuple(sorted(legs, key=lambda leg: _tf_sort_key(leg.timeframe)))
    total = len(ordered)

    if total == 0:
        return ConfluenceExplainSummary(
            symbol=symbol,
            legs=(),
            dominant_action=SignalAction.HOLD.value,
            agreeing_count=0,
            total=0,
            mean_confidence=0.0,
            is_unanimous=False,
            is_conflicted=False,
        )

    buy = [leg for leg in ordered if leg.action == SignalAction.BUY.value]
    sell = [leg for leg in ordered if leg.action == SignalAction.SELL.value]
    hold = [leg for leg in ordered if leg.action == SignalAction.HOLD.value]

    dominant = _dominant_action(len(buy), len(sell), len(hold))
    lead_legs = _lead_legs(dominant, buy, sell, hold)
    mean_conf = sum(leg.confidence for leg in lead_legs) / len(lead_legs) if lead_legs else 0.0

    return ConfluenceExplainSummary(
        symbol=symbol,
        legs=ordered,
        dominant_action=dominant,
        agreeing_count=len(lead_legs),
        total=total,
        mean_confidence=mean_conf,
        is_unanimous=len({leg.action for leg in ordered}) == 1,
        is_conflicted=bool(buy) and bool(sell),
    )


def _dominant_action(buy: int, sell: int, hold: int) -> DominantAction:
    """Plurality action; an exact BUY/SELL top tie (both > 0) is MIXED."""
    if buy > sell and buy >= hold:
        return SignalAction.BUY.value
    if sell > buy and sell >= hold:
        return SignalAction.SELL.value
    if hold > buy and hold > sell:
        return SignalAction.HOLD.value
    return _MIXED


def _lead_legs(
    dominant: DominantAction,
    buy: list[ConfluenceLeg],
    sell: list[ConfluenceLeg],
    hold: list[ConfluenceLeg],
) -> list[ConfluenceLeg]:
    """The legs backing the headline confidence (larger of BUY/SELL when MIXED)."""
    if dominant == SignalAction.BUY.value:
        return buy
    if dominant == SignalAction.SELL.value:
        return sell
    if dominant == SignalAction.HOLD.value:
        return hold
    return buy if len(buy) >= len(sell) else sell
