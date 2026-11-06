"""Hunt-loop timeframe sweep sets (SoT).

The edge-hunt loop sweeps a HIGH set (trend / position timeframes) by default, or a LOW set (intraday).
Both ARE the training bands declared on the registry (``timeframe_bands``), so they can never drift
from it (no hand-copied literal list).

They are deliberately NOT a split of ``ALIGNMENT_TIMEFRAMES_ORDER``, which is what they were until
2026-10-11: that list is the banded timeframes PROD SERVES, and 1m is now trainable but unserved. A
split of the served list would have dropped the timeframe the owner had just asked to hunt.
"""

from __future__ import annotations

from typing import Final

from src.shared.constants.timeframe_bands import HIGHER_TIMEFRAMES, LOWER_TIMEFRAMES
from src.shared.constants.timeframes import ALIGNMENT_TIMEFRAMES_ORDER

#: Intraday sweep set — used when ``high_timeframes`` is False. The LTF band, DERIVED: this comment
#: does not get to be the authority on its members (it listed the pre-2h set for a day once).
HUNT_LOW_TIMEFRAMES: Final[tuple[str, ...]] = LOWER_TIMEFRAMES

#: Trend / position sweep set — the hunt default. The HTF band, likewise derived.
HUNT_HIGH_TIMEFRAMES: Final[tuple[str, ...]] = HIGHER_TIMEFRAMES

#: The whole trainable clock, LTF band then HTF band. Owner 2026-09-26: research sweeps
#: that were HTF-only or 1h+HTF must cover "FULL TIMEFRAMES (LTF + HTF)".
HUNT_ALL_TIMEFRAMES: Final[tuple[str, ...]] = (*HUNT_LOW_TIMEFRAMES, *HUNT_HIGH_TIMEFRAMES)


#: Owner 2026-08-13: the RESEARCH sweep goes up to 3d, and 1w is excluded because a week candle
#: leaves too few bars over the available history for honest train/test splits.
#:
#: 3d is deliberately NOT a training-band member (`TimeframeBand` is None for it), so it is not
#: served as a live signal timeframe and the cron does not watch its closes. Research sweeping it
#: is a different question from productising it, and conflating the two is how `2h`/`6h` ended up
#: half-shipped. If a 3d book ever earns promotion, that is a deliberate separate step.
RESEARCH_EXTRA_HIGH_TIMEFRAMES: Final[tuple[str, ...]] = ("3d",)

#: The HTF sweep set for RESEARCH: the HTF band plus the extras above. 1w is absent because it is
#: in no band and not listed here — exclusion by construction, not by remembering to omit it.
RESEARCH_HIGH_TIMEFRAMES: Final[tuple[str, ...]] = (*HUNT_HIGH_TIMEFRAMES, *RESEARCH_EXTRA_HIGH_TIMEFRAMES)

#: The LTF sweep set for RESEARCH — exactly the LOWER band.
RESEARCH_LOW_TIMEFRAMES: Final[tuple[str, ...]] = HUNT_LOW_TIMEFRAMES

#: Owner 2026-08-09: 1h ML/features/combos are in-bounds for the research sweep, on top of the
#: full HTF band. Named because it is a DELIBERATE choice, not a derivable one.
DOLLAR_HUNT_ENTRY_TIMEFRAME: Final = "1h"

#: The dollar-hunt sweep set: the entry timeframe above plus every HTF band member.
#:
#: WHY THIS EXISTS. Two hypotheses spelled "1h" as ``HUNT_LOW_TIMEFRAMES[-1]`` — correct on the
#: day it was written, and silently wrong the moment 2h joined the low band, which is how they
#: began sweeping 2h and stopped sweeping the 1h the owner had explicitly asked for. Reading a
#: derived list BY POSITION is the same defect that made two cert sweeps cover 2 and 3 leverage
#: lanes out of seven. Intent gets a name; positions get nothing.
DOLLAR_HUNT_TIMEFRAMES: Final[tuple[str, ...]] = (DOLLAR_HUNT_ENTRY_TIMEFRAME, *HUNT_HIGH_TIMEFRAMES)

if DOLLAR_HUNT_ENTRY_TIMEFRAME not in HUNT_ALL_TIMEFRAMES:  # fail fast, not at hunt time
    _msg = f"DOLLAR_HUNT_ENTRY_TIMEFRAME {DOLLAR_HUNT_ENTRY_TIMEFRAME!r} is not a trainable timeframe"
    raise ValueError(_msg)


def select_hunt_timeframes(*, high_timeframes: bool = True) -> tuple[str, ...]:
    """Timeframe sweep set for the hunt loop — the TRAINABLE bands, not the research sweep.

    Deliberately returns ``HUNT_*`` rather than ``RESEARCH_*``: 3d is swept by the offline research
    grid but is not a training-band member, so the loop must not quietly start emitting a timeframe
    that nothing downstream can serve. Sweeping and productising are separate decisions.
    """
    return HUNT_HIGH_TIMEFRAMES if high_timeframes else HUNT_LOW_TIMEFRAMES


#: Owner 2026-08-25: TG signal notifications cover the whole clock prod generates signals on, LTF
#: and HTF. That is ``ALIGNMENT_TIMEFRAMES_ORDER`` -- the banded timeframes prod SERVES -- derived from
#: the registry, so a newly served band member is notifiable the day it is served rather than the
#: day someone remembers this line. 1m is trainable since 2026-10-11 but unserved: the cron makes no
#: 1m signals, so there is nothing on 1m to notify about.
TELEGRAM_NOTIFY_DEFAULT_TIMEFRAMES: Final[tuple[str, ...]] = ALIGNMENT_TIMEFRAMES_ORDER

#: Bulkowski pattern fires are NOT the same question, and this is why they get their own name.
#: The notify allowlist above is "which closes may reach the user at all" — the owner's call.
#: THIS is "on which timeframes does a chart-pattern fire carry evidence", and that one is
#: answered by measurement: `edge_lab/CERT_INVENTORY.md` records LTF (5m→2h) best-cell PnL as
#: ALL NEGATIVE. Widening notifications must not silently start firing pattern alerts on the
#: band where the corpus says they lose money.
BULKOWSKI_PATTERN_NOTIFY_TIMEFRAMES: Final[tuple[str, ...]] = HUNT_HIGH_TIMEFRAMES


def is_bulkowski_pattern_notify_timeframe(timeframe: str) -> bool:
    """True when Bulkowski pattern fires should merge into classic_sources / TG Fired:."""
    return timeframe in BULKOWSKI_PATTERN_NOTIFY_TIMEFRAMES


__all__ = [
    "BULKOWSKI_PATTERN_NOTIFY_TIMEFRAMES",
    "DOLLAR_HUNT_ENTRY_TIMEFRAME",
    "DOLLAR_HUNT_TIMEFRAMES",
    "HUNT_ALL_TIMEFRAMES",
    "HUNT_HIGH_TIMEFRAMES",
    "HUNT_LOW_TIMEFRAMES",
    "RESEARCH_EXTRA_HIGH_TIMEFRAMES",
    "RESEARCH_HIGH_TIMEFRAMES",
    "RESEARCH_LOW_TIMEFRAMES",
    "TELEGRAM_NOTIFY_DEFAULT_TIMEFRAMES",
    "is_bulkowski_pattern_notify_timeframe",
    "select_hunt_timeframes",
]
