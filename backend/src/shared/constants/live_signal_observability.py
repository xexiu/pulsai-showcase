"""Rolling window definitions for live-signal compact admin/health observability.

SoT for which windows are aggregated (label + minutes). First entry is
``primary_window`` for threshold badges in the compact view.

@see src.infrastructure.observability.live_signal_metrics.get_live_signal_compact_health_view
"""

from __future__ import annotations

from typing import Final

# Ordered: first tuple is primary_window for queue/persist/tier status badges.
LIVE_SIGNAL_COMPACT_METRIC_WINDOWS_MINUTES: Final[tuple[tuple[str, int], ...]] = (
    ("15m", 15),
    ("1h", 60),
)

# Redis sample lists: workers append, API reads (cross-process compact health).
LIVE_SIGNAL_OBS_REDIS_LIST_MAX_LEN: Final[int] = 4_000
LIVE_SIGNAL_OBS_REDIS_TTL_SECONDS: Final[int] = 3_600

__all__ = [
    "LIVE_SIGNAL_COMPACT_METRIC_WINDOWS_MINUTES",
    "LIVE_SIGNAL_OBS_REDIS_LIST_MAX_LEN",
    "LIVE_SIGNAL_OBS_REDIS_TTL_SECONDS",
]
