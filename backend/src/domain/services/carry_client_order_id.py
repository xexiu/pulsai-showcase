"""Deterministic, venue-safe ``clientOrderId`` for carry legs (idempotency / dedup).

WHY this exists:
  Same-CEX delta-neutral carry places market orders on every rebalance tick. With
  no client order id (the pre-existing behaviour of :class:`CcxtCarryOrderPlacer`),
  a retried tick — network blip, worker recycle mid-tick, Celery redelivery — can
  DOUBLE-PLACE a leg, breaking delta-neutrality with real funds.

  A ``clientOrderId`` that is DETERMINISTIC for the same logical leg
  ``(venue, symbol, side, reduce_only)`` within the same rebalance-window
  ``bucket`` lets the venue dedup: re-sending the same id returns the existing
  order instead of opening a new one (Bitget ``clientOid`` / Binance
  ``newClientOrderId`` map through CCXT's unified ``clientOrderId`` — see
  ``shared/constants/ccxt_params.py``).

  DISTINCT across ticks: a new ``bucket`` (the next rebalance window) yields a new
  id, so a genuine re-hedge is NOT suppressed. Venues recycle client ids after a
  window, so window-scoped ids never collide with stale orders.

Mirrors the compound-v2 leg-id pattern (``compound_v2_schedule.py``); venue-safety
(length ceiling) delegates to the shared :func:`ensure_outbound_ccxt_client_order_id`
SoT rather than re-implementing the cap here.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from src.domain.services.ccxt_order_client_id import ensure_outbound_ccxt_client_order_id
from src.shared.constants.carry import (
    CARRY_CLIENT_ORDER_ID_HASH_HEX_CHARS,
    CARRY_CLIENT_ORDER_ID_PREFIX,
    CARRY_REBALANCE_INTERVAL_MINUTES,
)

__all__ = ["build_carry_flatten_bucket", "build_carry_leg_client_order_id", "carry_rebalance_window_bucket"]


def build_carry_flatten_bucket(*, venue: str, base: str, now: datetime) -> str:
    """Idempotency bucket for a one-shot admin flatten (distinct from rebalance ticks).

    Retries within the same UTC second share a bucket so a flaky flatten does not
    double-place legs; separate flatten invocations get distinct buckets.

    RESTORED 2026-08-07. It was added by `23efbca02 feat(trading): send clientOid on every
    outbound order path`, then removed while its test stayed behind (an ImportError nobody
    noticed because that test could no longer be collected). With it gone, `run_carry_flatten`
    placed the admin flatten legs with NO clientOid, so a retried flatten could double-place —
    on the one path whose whole job is closing a live leveraged position.
    """
    return f"flatten|{venue.strip().lower()}|{base.strip().upper()}|{int(now.timestamp())}"


_REDUCE_ONLY_MARKER = "ro"
_OPEN_MARKER = "open"
_SEED_SEP = "|"
_SECONDS_PER_MINUTE = 60


def build_carry_leg_client_order_id(
    *,
    venue: str,
    symbol: str,
    side: str,
    reduce_only: bool,
    bucket: str,
) -> str:
    """Return a deterministic, venue-safe ``clientOrderId`` for one carry leg.

    Identical ``(venue, symbol, side, reduce_only, bucket)`` → identical id, so a
    retried tick dedups at the venue. A different ``bucket`` (next rebalance window)
    → different id, so a legitimate re-hedge still places. Case-insensitive on
    ``venue`` / ``side`` so casing drift cannot fork the id.

    Args:
        venue: Carry venue (e.g. ``"bitget"``).
        symbol: Unified CCXT symbol — encodes the leg (perp carries ``":"``).
        side: ``"buy"`` | ``"sell"``.
        reduce_only: Whether the order may only shrink the position.
        bucket: Idempotency-window seed (stable across retries, distinct per tick).
    """
    seed = _SEED_SEP.join(
        (
            venue.strip().lower(),
            symbol.strip(),
            side.strip().lower(),
            _REDUCE_ONLY_MARKER if reduce_only else _OPEN_MARKER,
            bucket,
        )
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:CARRY_CLIENT_ORDER_ID_HASH_HEX_CHARS]
    return ensure_outbound_ccxt_client_order_id(f"{CARRY_CLIENT_ORDER_ID_PREFIX}-{digest}")


def carry_rebalance_window_bucket(now: datetime) -> str:
    """Idempotency bucket = the current rebalance-window index.

    Two ticks (or retries) inside the same ``CARRY_REBALANCE_INTERVAL_MINUTES``
    window share a bucket → same leg ``clientOrderId`` → the venue dedups a
    re-sent order. The next window yields a new bucket so a genuine re-hedge
    still places. Pure function of ``now`` (no clock read here) so it is
    unit-testable without freezing time.
    """
    window_seconds = CARRY_REBALANCE_INTERVAL_MINUTES * _SECONDS_PER_MINUTE
    return str(int(now.timestamp()) // window_seconds)
