"""Subsystem names for the trading-activity poller gate (SoT).

Polling tasks (demo brackets, paper brackets, paper pending fills, paper
limit-order lifecycle) gate their expensive work on a Redis EXISTS check
against one of these names. Names are kebab-/snake-stable strings rather
than enum members so they survive Redis-key inspection / SCAN sessions
verbatim.

Why one constant per subsystem (and not a generic enum):
- pollers must NEVER gate on each other's activity, so each flag is
  namespaced separately;
- a typo at a poll site would be caught at import time rather than
  silently writing to the wrong key.

@see :class:`src.infrastructure.cache.keys.CacheKeys.trading_activity_flag`
@see :mod:`src.infrastructure.cache.trading_activity_flags`
"""

from __future__ import annotations

from typing import Final

TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS: Final[str] = "demo_brackets"
"""Gate for the demo-trading bracket poller (``check_demo_limit_orders``)."""

TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS: Final[str] = "paper_pending_fills"
"""Gate for the paper-trading pending-fill resolver."""

TRADING_ACTIVITY_SYSTEM_PAPER_LIMIT_LIFECYCLE: Final[str] = "paper_limit_lifecycle"
"""Gate for the paper-trading limit-order lifecycle sync."""

__all__ = [
    "TRADING_ACTIVITY_SYSTEM_DEMO_BRACKETS",
    "TRADING_ACTIVITY_SYSTEM_PAPER_LIMIT_LIFECYCLE",
    "TRADING_ACTIVITY_SYSTEM_PAPER_PENDING_FILLS",
]
