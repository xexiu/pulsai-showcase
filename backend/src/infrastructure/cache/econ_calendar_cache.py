"""Redis caches that decouple economic calendar consumers from FRED upstream.

Two snapshots:
- ``EconScheduleSnapshot`` — FOMC/CPI/NFP release dates from FRED ``release_dates``
- ``FredObservationsSnapshot`` — Latest CPI/NFP/FedFunds observation pairs

Writers (Celery beat warmers in :mod:`src.workers.tasks.econ_calendar_refresh_tasks`)
own upstream rate-budget. Readers (econ_event_alerts) treat ``None`` as "not yet
warm" and MUST NOT fall back to FRED — that fallback is exactly what produced
the 429 cascade we are eliminating.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from src.infrastructure.cache.keys import CacheKeys

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EconScheduleSnapshot:
    """FRED-derived release schedule (UTC, sorted)."""

    fomc: tuple[datetime, ...]
    cpi: tuple[datetime, ...]
    nfp: tuple[datetime, ...]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fomc": [dt.isoformat() for dt in self.fomc],
            "cpi": [dt.isoformat() for dt in self.cpi],
            "nfp": [dt.isoformat() for dt in self.nfp],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> EconScheduleSnapshot:
        return cls(
            fomc=_parse_iso_list(data.get("fomc")),
            cpi=_parse_iso_list(data.get("cpi")),
            nfp=_parse_iso_list(data.get("nfp")),
            updated_at=str(data.get("updated_at") or ""),
        )


@dataclass(frozen=True)
class FredObservationsSnapshot:
    """FRED latest-observation pairs (newest first) for CPI/NFP/FedFunds."""

    cpi_pair: tuple[tuple[date, float], ...]
    nfp_pair: tuple[tuple[date, float], ...]
    fed_funds_pair: tuple[tuple[date, float], ...]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpi_pair": _encode_obs_pair(self.cpi_pair),
            "nfp_pair": _encode_obs_pair(self.nfp_pair),
            "fed_funds_pair": _encode_obs_pair(self.fed_funds_pair),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> FredObservationsSnapshot:
        return cls(
            cpi_pair=_decode_obs_pair(data.get("cpi_pair")),
            nfp_pair=_decode_obs_pair(data.get("nfp_pair")),
            fed_funds_pair=_decode_obs_pair(data.get("fed_funds_pair")),
            updated_at=str(data.get("updated_at") or ""),
        )

    def cpi_as_list(self) -> list[tuple[date, float]]:
        return list(self.cpi_pair)

    def nfp_as_list(self) -> list[tuple[date, float]]:
        return list(self.nfp_pair)

    def fed_funds_as_list(self) -> list[tuple[date, float]]:
        return list(self.fed_funds_pair)


# ---------------------------- Redis I/O ------------------------------------


async def get_econ_schedule() -> EconScheduleSnapshot | None:
    """Read econ schedule snapshot. Returns ``None`` on miss or decode failure."""
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        raw = await redis.get_json(CacheKeys.econ_schedule())
        if not isinstance(raw, dict):
            return None
        return EconScheduleSnapshot.from_dict(raw)
    except Exception as exc:
        logger.warning("Econ schedule read skipped: %s", exc)
        return None


async def set_econ_schedule(snapshot: EconScheduleSnapshot) -> None:
    """Write econ schedule snapshot under centralized key + TTL."""
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        await redis.set_json(
            CacheKeys.econ_schedule(),
            snapshot.to_dict(),
            ex=CacheKeys.TTL_ECON_SCHEDULE,
        )
    except Exception as exc:
        logger.warning("Econ schedule write skipped: %s", exc)


async def get_fred_observations() -> FredObservationsSnapshot | None:
    """Read FRED observations snapshot. Returns ``None`` on miss or decode failure."""
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        raw = await redis.get_json(CacheKeys.fred_observations())
        if not isinstance(raw, dict):
            return None
        return FredObservationsSnapshot.from_dict(raw)
    except Exception as exc:
        logger.warning("FRED observations read skipped: %s", exc)
        return None


async def set_fred_observations(snapshot: FredObservationsSnapshot) -> None:
    """Write FRED observations snapshot under centralized key + TTL."""
    try:
        from src.infrastructure.cache.redis_client import get_redis_client

        redis = await get_redis_client()
        await redis.set_json(
            CacheKeys.fred_observations(),
            snapshot.to_dict(),
            ex=CacheKeys.TTL_FRED_OBSERVATIONS,
        )
    except Exception as exc:
        logger.warning("FRED observations write skipped: %s", exc)


# ---------------------------- Codec helpers --------------------------------


def _parse_iso_list(raw: object) -> tuple[datetime, ...]:
    if not isinstance(raw, list):
        return ()
    out: list[datetime] = []
    for entry in raw:
        if not isinstance(entry, str):
            continue
        try:
            parsed = datetime.fromisoformat(entry)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        out.append(parsed)
    out.sort()
    return tuple(out)


_OBS_PAIR_TUPLE_LEN = 2  # JSON-encoded observation pair: ``[iso_date, value]``.


def _encode_obs_pair(pair: tuple[tuple[date, float], ...]) -> list[list[Any]]:
    return [[d.isoformat(), float(v)] for d, v in pair]


def _decode_obs_pair(raw: object) -> tuple[tuple[date, float], ...]:
    if not isinstance(raw, list):
        return ()
    out: list[tuple[date, float]] = []
    for entry in raw:
        if not isinstance(entry, list) or len(entry) != _OBS_PAIR_TUPLE_LEN:
            continue
        d_raw, v_raw = entry[0], entry[1]
        if not isinstance(d_raw, str):
            continue
        try:
            d_val = date.fromisoformat(d_raw)
            v_val = float(v_raw)
        except ValueError, TypeError:
            continue
        out.append((d_val, v_val))
    return tuple(out)
