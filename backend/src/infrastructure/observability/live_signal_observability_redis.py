"""
Redis-backed live-signal observation buffer (worker write, API read).

Workers append JSON samples via sync Redis; the API merges them with any
in-process samples when building the compact admin health view.

@see src.infrastructure.observability.live_signal_metrics
@see src.infrastructure.cache.on_chain_snapshot (same worker-write / API-read pattern)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import orjson

from src.infrastructure.cache.keys import CacheKeys
from src.infrastructure.observability.live_signal_metrics import (
    _MetricsWindowState,
    _TimedTier,
    _TimedValue,
)
from src.shared.constants.live_signal_observability import (
    LIVE_SIGNAL_OBS_REDIS_LIST_MAX_LEN,
    LIVE_SIGNAL_OBS_REDIS_TTL_SECONDS,
)
from src.shared.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


def _encode_sample(*, at_iso: str, value: float | None = None, tier: str | None = None, timeframe: str | None = None) -> str:
    payload: dict[str, Any] = {"at": at_iso}
    if value is not None:
        payload["v"] = value
    if tier is not None:
        payload["tier"] = tier
    if timeframe is not None:
        payload["tf"] = timeframe
    return orjson.dumps(payload).decode()


def _parse_at(raw_at: str) -> Any:
    parsed = datetime.fromisoformat(raw_at)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=utc_now().tzinfo)
    return parsed


def _redis_list_append(key: str, encoded: str) -> None:
    from src.infrastructure.cache.redis_connections import create_sync_redis_client

    client = create_sync_redis_client()
    try:
        pipe = client.pipeline()
        pipe.lpush(key, encoded)
        pipe.ltrim(key, 0, LIVE_SIGNAL_OBS_REDIS_LIST_MAX_LEN - 1)
        pipe.expire(key, LIVE_SIGNAL_OBS_REDIS_TTL_SECONDS)
        pipe.execute()
    except Exception as exc:
        logger.warning("live_signal_obs_redis_append_skipped key=%s err=%s", key, exc)
    finally:
        client.close()


def append_queue_wait_sample_sync(queue_wait_seconds: float, timeframe: str | None = None) -> None:
    """Record one queue-wait sample (Celery worker). Fails open on Redis errors."""
    _redis_list_append(
        CacheKeys.live_signal_obs_queue_wait(),
        _encode_sample(at_iso=utc_now().isoformat(), value=queue_wait_seconds, timeframe=timeframe),
    )


def append_persist_commit_sample_sync(duration_seconds: float, timeframe: str | None = None) -> None:
    """Record one persist+commit duration sample (Celery worker)."""
    _redis_list_append(
        CacheKeys.live_signal_obs_persist_commit(),
        _encode_sample(at_iso=utc_now().isoformat(), value=duration_seconds, timeframe=timeframe),
    )


def append_persist_error_sample_sync(timeframe: str | None = None) -> None:
    """Record one persist/commit error (Celery worker)."""
    _redis_list_append(
        CacheKeys.live_signal_obs_persist_errors(),
        _encode_sample(at_iso=utc_now().isoformat(), value=1.0, timeframe=timeframe),
    )


def append_ohlcv_tier_sample_sync(tier: str, timeframe: str | None = None) -> None:
    """Record one OHLCV tier choice (Celery worker / shared OHLCV helper)."""
    _redis_list_append(
        CacheKeys.live_signal_obs_ohlcv_tier(),
        _encode_sample(at_iso=utc_now().isoformat(), tier=tier, timeframe=timeframe),
    )


def _decode_timed_values(raw_items: list[str]) -> list[_TimedValue]:
    out: list[_TimedValue] = []
    for raw in raw_items:
        try:
            row = orjson.loads(raw)
        except orjson.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        at_raw = row.get("at")
        value = row.get("v")
        if not isinstance(at_raw, str) or not isinstance(value, (int, float)):
            continue
        tf = row.get("tf")
        timeframe = tf if isinstance(tf, str) else None
        out.append(_TimedValue(at=_parse_at(at_raw), value=float(value), timeframe=timeframe))
    return out


def _decode_timed_tiers(raw_items: list[str]) -> list[_TimedTier]:
    out: list[_TimedTier] = []
    for raw in raw_items:
        try:
            row = orjson.loads(raw)
        except orjson.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        at_raw = row.get("at")
        tier = row.get("tier")
        if not isinstance(at_raw, str) or not isinstance(tier, str):
            continue
        tf = row.get("tf")
        timeframe = tf if isinstance(tf, str) else None
        out.append(_TimedTier(at=_parse_at(at_raw), tier=tier, timeframe=timeframe))
    return out


def _fetch_list(key: str) -> list[str]:
    from src.infrastructure.cache.redis_connections import create_sync_redis_client

    client = create_sync_redis_client()
    try:
        items = client.lrange(key, 0, LIVE_SIGNAL_OBS_REDIS_LIST_MAX_LEN - 1)
        return list(items) if items else []
    except Exception as exc:
        logger.warning("live_signal_obs_redis_read_skipped key=%s err=%s", key, exc)
        return []
    finally:
        client.close()


def load_metrics_window_state_from_redis_sync() -> _MetricsWindowState:
    """Load worker-written samples for compact health (API process)."""
    queue_raw = _fetch_list(CacheKeys.live_signal_obs_queue_wait())
    persist_raw = _fetch_list(CacheKeys.live_signal_obs_persist_commit())
    errors_raw = _fetch_list(CacheKeys.live_signal_obs_persist_errors())
    tier_raw = _fetch_list(CacheKeys.live_signal_obs_ohlcv_tier())
    return _MetricsWindowState(
        queue_wait_observations=_decode_timed_values(queue_raw),
        persist_commit_observations=_decode_timed_values(persist_raw),
        persist_commit_errors=_decode_timed_values(errors_raw),
        ohlcv_tier_events=_decode_timed_tiers(tier_raw),
    )


def merge_metrics_window_states(*states: _MetricsWindowState) -> _MetricsWindowState:
    """Concatenate observation buffers (e.g. Redis + in-process smoke samples)."""
    merged = _MetricsWindowState()
    for state in states:
        merged.queue_wait_observations.extend(state.queue_wait_observations)
        merged.persist_commit_observations.extend(state.persist_commit_observations)
        merged.persist_commit_errors.extend(state.persist_commit_errors)
        merged.ohlcv_tier_events.extend(state.ohlcv_tier_events)
    return merged


__all__ = [
    "append_ohlcv_tier_sample_sync",
    "append_persist_commit_sample_sync",
    "append_persist_error_sample_sync",
    "append_queue_wait_sample_sync",
    "load_metrics_window_state_from_redis_sync",
    "merge_metrics_window_states",
]
