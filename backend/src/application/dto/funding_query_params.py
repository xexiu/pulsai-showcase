"""Shared query-param parsing + defaults for the funding-carry endpoints (PulsAI Carry).

SoT for the monitor / backtest / paper endpoints' common request surface — CSV parsing, the
base-count cap, and the default symbol/venue/leverage strings — so the three endpoints don't
duplicate the idioms (CODING_STANDARDS §2 NO-DRY, §12 centralized constants).
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Final

from src.shared.constants.carry import (
    CARRY_MAX_LEVERAGE,
    DEFAULT_CARRY_DAYS,
    DEFAULT_CARRY_VENUES_CSV,
    MAX_CARRY_DAYS,
    MIN_CARRY_DAYS,
)

# Shared request defaults + caps (one source for all three funding endpoints).
MAX_CARRY_BASES = 10  # abuse/cost guard: cap the per-request base-asset fan-out
DEFAULT_CARRY_SYMBOLS = "BTC,ETH"
# Re-export canonical carry constants so endpoints import one module, not two.
DEFAULT_CARRY_VENUES = DEFAULT_CARRY_VENUES_CSV
DEFAULT_BACKTEST_LEVERAGES = "1,2,3,5,8"

# Per-(venue, base) wall-clock deadline for the funding read-model endpoints. They
# fan out one task per (venue, base) and run them concurrently; each task is bounded
# by this deadline so a single slow/hanging venue is skipped fast instead of dragging
# the whole request past the frontend proxy's ~30s cap. This is an endpoint fan-out
# budget (presentation concern), so it lives here with the other request defaults —
# not in the carry domain constants. Sized well under 30s with headroom for the
# concurrent cold (cache-miss) fan-out.
FUNDING_COMBO_DEADLINE_SECONDS: Final[float] = 12.0

__all__ = [
    "CARRY_MAX_LEVERAGE",
    "DEFAULT_BACKTEST_LEVERAGES",
    "DEFAULT_CARRY_DAYS",
    "DEFAULT_CARRY_SYMBOLS",
    "DEFAULT_CARRY_VENUES",
    "FUNDING_COMBO_DEADLINE_SECONDS",
    "MAX_CARRY_BASES",
    "MAX_CARRY_DAYS",
    "MIN_CARRY_DAYS",
    "parse_csv",
    "parse_leverages",
    "resolve_bases",
    "resolve_venues",
]


def parse_csv(raw: str) -> list[str]:
    """Split a comma-separated query value into trimmed, non-empty tokens."""
    return [p.strip() for p in raw.split(",") if p.strip()]


def resolve_bases(symbols: str) -> list[str]:
    """Normalise a ``symbols`` CSV into the base assets a funding request will actually read.

    The three funding endpoints each applied this same line, and so must anything that wants to
    PREDICT what they will read — a boot prewarm that guesses a different base set seeds cache keys
    nobody asks for and looks successful while warming nothing.
    """
    return [b.upper() for b in parse_csv(symbols)][:MAX_CARRY_BASES]


def resolve_venues(venues: str, supported: Collection[str]) -> list[str]:
    """Normalise a ``venues`` CSV down to the ones this deployment can actually query.

    ``supported`` is INJECTED rather than imported: this is an application DTO, and reaching into
    ``infrastructure.exchange`` from here would point a dependency outward across the layer
    boundary (`docs/04-structural/DDD_PATTERNS.md`). Request order is preserved, not the
    supported-set's order — the caller asked in a particular order and the fan-out honours it.
    """
    supported_lower = {v.lower() for v in supported}
    return [v.lower() for v in parse_csv(venues) if v.lower() in supported_lower]


def parse_leverages(raw: str) -> list[float]:
    """Parse a CSV of positive leverages; silently skips non-numeric / non-positive tokens."""
    out: list[float] = []
    for part in parse_csv(raw):
        try:
            lev = float(part)
        except ValueError:
            continue
        if lev > 0.0:
            out.append(lev)
    return out
