"""Extract venue client order identifiers from CCXT unified order dicts.

CCXT surfaces user-supplied ids as ``clientOrderId`` on both requests and
responses; venues (Bitget ``clientOid``, Binance ``newClientOrderId``) map
through that unified field.

Outbound placement uses :func:`ensure_outbound_ccxt_client_order_id` so every
``create_order`` carries a non-empty client id (explicit or generated).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from src.shared.constants.ccxt_params import CCXT_PARAM_CLIENT_ORDER_ID
from src.shared.constants.paper_trading import (
    CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_FIRST,
    CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_SECOND,
    CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX,
    CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN,
    PAPER_ORDER_VENUE_CLIENT_ORDER_ID_MAX_LEN,
)

__all__ = [
    "ensure_outbound_ccxt_client_order_id",
    "resolve_persisted_venue_client_order_id",
    "venue_client_order_id_from_ccxt_order",
]


def ensure_outbound_ccxt_client_order_id(explicit: str | None) -> str:
    """Return a venue-safe ``clientOrderId`` for every CCXT ``create_order``.

    When ``explicit`` is missing or blank, generates a unique fallback
    (prefix :data:`~src.shared.constants.paper_trading.CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX`
    + UUID material) and truncates to
    :data:`~src.shared.constants.paper_trading.CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN`
    so Binance's 36-char ceiling is respected.
    """
    if explicit is not None:
        trimmed = str(explicit).strip()
        if trimmed:
            return trimmed[:CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN]
    return _generate_fallback_ccxt_client_order_id()


def _generate_fallback_ccxt_client_order_id() -> str:
    a = uuid.uuid4().hex[:CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_FIRST]
    b = uuid.uuid4().hex[:CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_SECOND]
    raw = f"{CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX}-{a}-{b}"
    return raw[:CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN]


def resolve_persisted_venue_client_order_id(
    ccxt_response: Mapping[str, Any] | None,
    *,
    outbound_client_order_id: str | None,
) -> str | None:
    """Pick the id to store on ``paper_orders.venue_client_order_id``.

    Prefer the unified ``clientOrderId`` echoed on the **placement response**
    (exchange truth). If the venue omits it on the immediate payload, fall
    back to ``outbound_client_order_id`` — the same string already passed
    through :func:`ensure_outbound_ccxt_client_order_id` at the adapter
    boundary — so DB correlation stays stable without an extra ``fetch_order``.
    """
    echoed = venue_client_order_id_from_ccxt_order(ccxt_response)
    if echoed:
        return echoed
    if outbound_client_order_id is None:
        return None
    text = str(outbound_client_order_id).strip()
    if not text:
        return None
    max_len = PAPER_ORDER_VENUE_CLIENT_ORDER_ID_MAX_LEN
    if len(text) > max_len:
        return text[:max_len]
    return text


def venue_client_order_id_from_ccxt_order(ccxt_order: Mapping[str, Any] | None) -> str | None:
    """Return normalized client order id for persistence, or ``None`` if absent.

    Truncates to :data:`~src.shared.constants.paper_trading.PAPER_ORDER_VENUE_CLIENT_ORDER_ID_MAX_LEN`
    so values always fit ``paper_orders.venue_client_order_id`` — venues enforce
    their own shorter ceilings; truncation is a last-resort guardrail.
    """
    if not ccxt_order:
        return None
    raw = ccxt_order.get(CCXT_PARAM_CLIENT_ORDER_ID)
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    max_len = PAPER_ORDER_VENUE_CLIENT_ORDER_ID_MAX_LEN
    if len(text) > max_len:
        return text[:max_len]
    return text
