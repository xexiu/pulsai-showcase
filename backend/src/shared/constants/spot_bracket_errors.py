"""Stable machine codes for spot SL/TP (plan/conditional) attachment outcomes.

FE maps these to i18n; logs and analytics use the same strings. Do not change
existing values without a migration note — they cross the HTTP boundary.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "SPOT_BRACKET_NOT_IMPLEMENTED",
    "SPOT_BRACKET_SPOT_SELL_BRACKET",
    "SPOT_BRACKET_UNSUPPORTED_VENUE",
]

SPOT_BRACKET_UNSUPPORTED_VENUE: Final[str] = "SPOT_BRACKET_UNSUPPORTED_VENUE"
"""Venue + market type has no registered spot plan-bracket strategy."""

SPOT_BRACKET_NOT_IMPLEMENTED: Final[str] = "SPOT_BRACKET_NOT_IMPLEMENTED"
"""Registered for the exchange but concrete plan placement is not shipped yet."""

SPOT_BRACKET_SPOT_SELL_BRACKET: Final[str] = "SPOT_BRACKET_SPOT_SELL_BRACKET"
"""Paper/live spot sell with SL/TP is not supported (v1 targets buy + exit plans)."""
