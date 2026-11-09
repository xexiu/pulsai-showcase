"""Redis cache for FRED daily macro series (VIX / DGS10 / DXY).

Sibling of :mod:`econ_calendar_cache`: both isolate FRED upstream from per-tick
beat consumers. This snapshot is the third (and final) FRED warmer cache —
``macro_snapshot_tasks`` now reads VIX/Treasury/DXY from here instead of
calling :class:`FredMacroProvider.fetch_latest` directly each refresh.

Writer: :mod:`src.workers.tasks.fred_macro_series_refresh_tasks`.
Reader: :mod:`src.workers.tasks.macro_snapshot_tasks` (sentiment snapshot).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.infrastructure.cache.keys import CacheKeys
from src.shared.utils.decimal_safe import float_or_none

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FredMacroSeriesSnapshot:
    """Latest close values for FRED daily macro series."""

    vix_close: float | None
    treasury_10y: float | None
    dxy_close: float | None
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "vix_close": self.vix_close,
            "treasury_10y": self.treasury_10y,
            "dxy_close": self.dxy_close,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> FredMacroSeriesSnapshot:
        return cls(
            vix_close=float_or_none(data.get("vix_close")),
            treasury_10y=float_or_none(data.get("treasury_10y")),
            dxy_close=float_or_none(data.get("dxy_close")),
            updated_at=str(data.get("updated_at") or ""),
        )


async def get_fred_macro_series() -> FredMacroSeriesSnapshot | None:
    """Read FRED macro-series snapshot. Returns ``None`` on miss/decode failure."""
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        raw = await redis.get_json(CacheKeys.fred_macro_series())
        if not isinstance(raw, dict):
            return None
        return FredMacroSeriesSnapshot.from_dict(raw)
    except Exception as exc:
        logger.warning("FRED macro series read skipped: %s", exc)
        return None


async def set_fred_macro_series(snapshot: FredMacroSeriesSnapshot) -> None:
    """Write FRED macro-series snapshot under centralized key + TTL."""
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        await redis.set_json(
            CacheKeys.fred_macro_series(),
            snapshot.to_dict(),
            ex=CacheKeys.TTL_FRED_MACRO_SERIES,
        )
    except Exception as exc:
        logger.warning("FRED macro series write skipped: %s", exc)
