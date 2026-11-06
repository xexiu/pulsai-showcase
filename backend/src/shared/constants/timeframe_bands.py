"""LOWER vs HIGHER timeframe bands — the band VOCABULARY, derived from the registry.

Owner spec (2026-08-12, GRID-SUBSET: dated quote): *"lower timeframes are 5m,15m,30m,1h,2h and Higher timeframes are
4h,6h,8h,12h,1d ... SoT, centralized ... so later can train ML on HTF / on LTF shared SoT from
BE"*. Extended 2026-10-11: *"add 1min to LTF"*.

WHERE THE DECLARATION LIVES, AND WHY NOT HERE. Membership is declared once, per timeframe, as the
``band`` field on ``TimeframeDefinition`` in `timeframes.py` — the same shape that module already
uses for ``open_alignment``. This module holds the band *vocabulary* and the lookup helpers, and
derives every list below from that field.

The first version of this file declared its own ``_LOWER_RAW`` / ``_HIGHER_RAW`` tuples. That was
the defect it was written to prevent, one level up: a second copy of the registry, free to drift
from it. It did drift within a day — `2h` and `6h` were added to both this file and the registry
and to nothing else, so they were absent from the labels (a bare ``KeyError`` in
``/config/public``), from the default supported list (no OHLCV sync, invisible to the frontend),
from ``VALID_TIMEFRAMES_SIGNAL_AND_TRAINING`` (untrainable) and from
``ALIGNMENT_TIMEFRAMES_ORDER`` (the cron never fired on their closes). Two tuples agreeing with
each other proved nothing, because the four lists that mattered were elsewhere.

The precedent this repo already paid for: ``CAPITAL_MODES`` listed spot/3x/5x/8x under a rule
mandating spot+3..8x, so 4x/6x/7x were never computed in any of 38 certs — and re-certifying on
the true ladder found ``perp_6x`` the best surviving lane on 12h (3.70x B&H, 415 trades, zero
liquidations). A list that is DERIVED cannot hide money that way.

MEMBERSHIP IS NOT A DURATION TEST. ``3d`` and ``1w`` are real, supported timeframes that belong to
neither band: they are chart/analysis timeframes, not grids we train or certify on. (``1m`` joined
the LOWER band on 2026-10-11; it stays unserved by default, which is a serving decision recorded on
``_DEFAULT_EXCLUDED_TIMEFRAMES``, not a band one.) The lookups below return ``None`` for them rather
than bucketing by length — silently sorting an unlisted timeframe into a band is how a model gets
trained on a grid nobody chose.

ALIGNMENT NOTE. Every member of both bands divides a UTC day evenly, so all of them use
``CandleOpenAlignment.EPOCH``. That is why 2h (12 buckets/day) and 6h (4 buckets/day) were safe to
add, and why ``3d`` — which needs its own Binance-phase alignment — sits outside these bands.
"""

from __future__ import annotations

from typing import Final

from src.shared.constants.timeframes import TIMEFRAME_REGISTRY, TimeframeBand

#: Band identifiers, re-exported so callers that only need the vocabulary do not import the
#: registry module. These are the ``TimeframeBand`` values, not parallel string literals — a
#: second spelling of "ltf" is exactly the drift this module exists to remove.
BAND_LOWER: Final = TimeframeBand.LOWER
BAND_HIGHER: Final = TimeframeBand.HIGHER


def _members(band: TimeframeBand) -> tuple[str, ...]:
    """Registry members of ``band``, shortest first (registry insertion order is the contract)."""
    return tuple(tf for tf, definition in TIMEFRAME_REGISTRY.items() if definition.band is band)


#: LTF training band, shortest first. Derived; declare membership in the registry, not here.
LOWER_TIMEFRAMES: Final[tuple[str, ...]] = _members(TimeframeBand.LOWER)

#: HTF training band, shortest first. Derived; declare membership in the registry, not here.
HIGHER_TIMEFRAMES: Final[tuple[str, ...]] = _members(TimeframeBand.HIGHER)


def band_for_timeframe(timeframe: str) -> TimeframeBand | None:
    """``TimeframeBand.LOWER`` / ``TimeframeBand.HIGHER``, or None outside both training bands.

    None is deliberately NOT a default band. ``3d``/``1w`` are supported chart timeframes we do not
    train or certify on, and an unknown string is a caller bug — bucketing any of them would hand a
    training run a grid nobody selected.
    """
    definition = TIMEFRAME_REGISTRY.get(timeframe)
    return definition.band if definition is not None else None


def is_higher_timeframe(timeframe: str) -> bool | None:
    """True for HTF, False for LTF, None when the timeframe is in neither band.

    None rather than False, for the same reason ``has_sufficient_track_record`` returns None:
    "not in a band" and "in the lower band" are different findings, and collapsing them makes an
    unclassified timeframe silently read as LTF.
    """
    band = band_for_timeframe(timeframe)
    if band is None:
        return None
    return band is TimeframeBand.HIGHER


__all__ = [
    "BAND_HIGHER",
    "BAND_LOWER",
    "HIGHER_TIMEFRAMES",
    "LOWER_TIMEFRAMES",
    "TimeframeBand",
    "band_for_timeframe",
    "is_higher_timeframe",
]
