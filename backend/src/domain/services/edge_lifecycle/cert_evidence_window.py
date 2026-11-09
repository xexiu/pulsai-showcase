"""Is a cert's window long enough for its number to mean anything?

The corpus screens trade COUNT (`MIN_TRADES_FOR_SHARPE`) and has never screened window LENGTH.
Measured 2026-08-12 across the 33 certs on disk, **16 have windows under 30 days** -- four of them
2 DAYS, and one of those is `1d gb_clf v2`, the LIVE PRODUCTION model, at 25 days. Their
`beats B&H` ratios (1.00x-1.10x) were ranked in the same table as a 587-day book's 2.47x, as if the
two claims were comparable.

A SHORT WINDOW IS NOT A KILL. It says nothing about the model; it says the CERT is uninformative.
Calling it "excluded" would repeat the error corrected twice on the same day -- v15's absent
`capital_modes` read as a verdict, v42's absent levers read as ruin. Missing evidence is owed a
MEASUREMENT, not a tombstone. So this module reports an EVIDENCE STATE, never a verdict, and
`is_sufficient` is None (never False) when the answer is unknown.

WHY BARS, NOT DAYS. Owner, on the trade floor: "shouldn't this be dynamic based on timeframes...
or inventing 100 magic number?" Measuring the window in BARS OF ITS OWN TIMEFRAME makes the floor
timeframe-aware by construction, and derives it from `MIN_TRADES_FOR_SHARPE` instead of inventing a
second constant: with sequential positions a book cannot take more trades than it has bars, so a
window shorter than the trade floor cannot reach that floor by that route.

    1d  -> 100 bars = 100 days        4h -> 100 bars ~ 16.7 days
    12h -> 100 bars =  50 days        1h -> 100 bars ~  4.2 days

HONEST LIMIT. With `max_open_positions = N`, up to N trades can open per bar, so the bound is not
strict -- a 50-concurrency book could book 100 trades across 2 bars. But those are 100 OVERLAPPING
bets on two bars of price action: one observation wearing a hundred hats, which is weaker evidence
rather than stronger. The bars floor is the right shape either way, and stating the leak beats
implying a rigour the measure does not have.

DDD: pure domain rules, no I/O (`DDD_PATTERNS.md` -- it gates whether a money claim is admissible,
so it carries business meaning). Timeframe duration comes from the shared
`TIMEFRAME_REGISTRY` SoT via `get_timeframe_ms`; this module defines no duration table of its own.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from src.domain.services.edge_lifecycle.gate import MIN_TRADES_FOR_SHARPE
from src.shared.constants.timeframes import get_timeframe_ms

logger = logging.getLogger(__name__)

#: Bars of the cert's OWN timeframe a window must span. Deliberately the SAME number as the trade
#: floor, not a new one: a book cannot take more sequential trades than it has bars, so the trade
#: floor implies this window floor. Keeping them equal means there is ONE knob to fix when
#: `MIN_TRADES_FOR_SHARPE` is eventually put on a proper (MinTRL-derived) footing.
MIN_WINDOW_BARS: Final[int] = MIN_TRADES_FOR_SHARPE

WINDOW_SUFFICIENT: Final = "sufficient"
WINDOW_TOO_SHORT: Final = "window_too_short"
#: NOT a failure state. Unknown endpoints or an unrecognised timeframe mean the question is
#: unanswerable, and an unanswerable question gets no answer rather than a flattering one.
WINDOW_UNKNOWN: Final = "window_unknown"

_MS_PER_DAY: Final = 86_400_000.0


@dataclass(frozen=True, slots=True)
class WindowEvidence:
    """The evidence state of a cert window, WITH the numbers behind it.

    Frozen because it is read across the cert/ledger/ship boundary and a mutable verdict object
    is how a measured state quietly becomes an edited one. Carrying `bars`, `span_days` and
    `required_bars` is deliberate: a state with no measurement attached is exactly the
    unverifiable assertion this repo keeps paying for.
    """

    timeframe: str
    span_days: float | None
    bars: float | None
    required_bars: int
    state: str

    @property
    def is_sufficient(self) -> bool | None:
        """True / False when measurable, None when unknown — never False for "unmeasured"."""
        if self.state == WINDOW_UNKNOWN:
            return None
        return self.state == WINDOW_SUFFICIENT


def window_bars(
    *,
    start: datetime | None,
    end: datetime | None,
    timeframe: str,
) -> float | None:
    """How many bars of `timeframe` the span covers. None when unanswerable.

    An inverted or empty span is 0.0, not a negative: "no window" is a real, measurable answer,
    while a negative bar count would be a nonsense number that downstream comparisons would
    silently treat as small-but-valid.
    """
    if start is None or end is None:
        return None

    try:
        tf_ms = float(get_timeframe_ms(timeframe))
    except KeyError, ValueError, TypeError:
        tf_ms = 0.0

    if tf_ms <= 0.0:
        # UNKNOWN, never assumed -- and SEEN: an open window is normal, a caller passing a timeframe
        # with no bar duration is a defect, and a bare None hid which one this was.
        logger.warning("window_bars: timeframe %r has no bar duration; bar count unknown", timeframe)
        return None

    span_ms = (end - start).total_seconds() * 1000.0
    if span_ms <= 0.0:
        return 0.0

    return span_ms / tf_ms


def assess_window_evidence(
    *,
    start: datetime | None,
    end: datetime | None,
    timeframe: str,
    min_bars: int = MIN_WINDOW_BARS,
) -> WindowEvidence:
    """Classify a cert window as sufficient / too short / unknown, with its measurements.

    Never returns a verdict on the BOOK — only on whether the window can support one.
    """
    bars = window_bars(start=start, end=end, timeframe=timeframe)

    span_days: float | None = None
    if start is not None and end is not None:
        span_days = max((end - start).total_seconds() * 1000.0, 0.0) / _MS_PER_DAY

    if bars is None:
        state = WINDOW_UNKNOWN
    elif bars >= float(min_bars):
        state = WINDOW_SUFFICIENT
    else:
        state = WINDOW_TOO_SHORT

    return WindowEvidence(
        timeframe=timeframe,
        span_days=span_days,
        bars=bars,
        required_bars=int(min_bars),
        state=state,
    )


#: The window key holding the model's FIT cutoff -- its metadata `test_end_date`, the date the cert
#: grid already stamps as `model_data_through` beside `model_trained_through`. The other axis of
#: "can this window be evidence": LENGTH above, and whether the model had already SEEN it here.
MODEL_DATA_THROUGH_KEY: Final = "model_data_through"


def confirm_window_fit_overlap(window: Mapping[str, Any]) -> str | None:
    """Why a confirm window cannot be evidence about its model, or None when the model never saw it.

    INSAMPLE-CONFIRM-1 (2026-09-24). Prod `1d gb_clf v2` was fit on every bar through 2026-07-16
    (next-bar hit-rate 0.82 before it, 0.478 after), yet its three pre-commitments confirmed from
    2025-09 and graded `candidate` as unseen -- the door measured "unseen" from the TRAINING start.
    23 of 77 records had a confirm window starting before their own model's cutoff.

    An unrecorded cutoff or start is not a pass: the boundary is unknown, so the window is too.
    """
    start, cutoff = _window_start_and_fit_cutoff(window)
    if not cutoff:
        return f"model fit cutoff ({MODEL_DATA_THROUGH_KEY}) not recorded — the confirm window cannot be shown unseen"
    if not start:
        return "confirm window start not recorded — it cannot be shown unseen"
    if confirm_window_in_sample(window):
        return f"confirm window starts {start}, before the model's data cutoff {cutoff} — in-sample, cannot prove the book"
    return None


def confirm_window_in_sample(window: Mapping[str, Any]) -> bool | None:
    """Did the model's fit see this confirm window? None when either bound is unrecorded.

    The one home of the date rule `confirm_window_fit_overlap` explains in words; money-standings
    stamps its answer on the row (WINDOW-SAMPLE-1) so a pre-commit never borrows its cert's flag.
    """
    start, cutoff = _window_start_and_fit_cutoff(window)
    if not start or not cutoff:
        return None
    return start < cutoff


def _window_start_and_fit_cutoff(window: Mapping[str, Any]) -> tuple[str, str]:
    """The confirm window's start and its model's fit cutoff, as ISO dates ('' when unrecorded)."""
    return str(window.get("start") or "")[:10], str(window.get(MODEL_DATA_THROUGH_KEY) or "")[:10]


__all__ = [
    "MIN_WINDOW_BARS",
    "MODEL_DATA_THROUGH_KEY",
    "WINDOW_SUFFICIENT",
    "WINDOW_TOO_SHORT",
    "WINDOW_UNKNOWN",
    "WindowEvidence",
    "assess_window_evidence",
    "confirm_window_fit_overlap",
    "confirm_window_in_sample",
    "window_bars",
]
