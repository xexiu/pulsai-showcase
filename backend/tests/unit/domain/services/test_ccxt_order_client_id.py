"""Behavior tests for :mod:`src.domain.services.ccxt_order_client_id`."""

from __future__ import annotations

from src.domain.services.ccxt_order_client_id import (
    ensure_outbound_ccxt_client_order_id,
    resolve_persisted_venue_client_order_id,
    venue_client_order_id_from_ccxt_order,
)
from src.shared.constants.ccxt_params import CCXT_PARAM_CLIENT_ORDER_ID
from src.shared.constants.paper_trading import (
    CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX,
    CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN,
    PAPER_ORDER_VENUE_CLIENT_ORDER_ID_MAX_LEN,
)


def test_returns_none_when_order_missing_or_empty_client_field() -> None:
    assert venue_client_order_id_from_ccxt_order(None) is None
    assert venue_client_order_id_from_ccxt_order({}) is None
    assert venue_client_order_id_from_ccxt_order({CCXT_PARAM_CLIENT_ORDER_ID: ""}) is None
    assert venue_client_order_id_from_ccxt_order({CCXT_PARAM_CLIENT_ORDER_ID: "   "}) is None


def test_returns_trimmed_echo_from_unified_ccxt_response() -> None:
    out = venue_client_order_id_from_ccxt_order({CCXT_PARAM_CLIENT_ORDER_ID: "  pam-k-abc  "})
    assert out == "pam-k-abc"


def test_truncates_to_configured_max_length() -> None:
    long_id = "x" * (PAPER_ORDER_VENUE_CLIENT_ORDER_ID_MAX_LEN + 12)
    out = venue_client_order_id_from_ccxt_order({CCXT_PARAM_CLIENT_ORDER_ID: long_id})
    assert len(out) == PAPER_ORDER_VENUE_CLIENT_ORDER_ID_MAX_LEN
    assert out == "x" * PAPER_ORDER_VENUE_CLIENT_ORDER_ID_MAX_LEN


def test_ensure_outbound_truncates_explicit_to_wire_cap() -> None:
    long_explicit = "y" * (CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN + 8)
    out = ensure_outbound_ccxt_client_order_id(long_explicit)
    assert len(out) == CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN


def test_resolve_prefers_echo_from_ccxt_response_over_outbound() -> None:
    """Placement payload wins when venue echoes our clientOrderId."""
    out = resolve_persisted_venue_client_order_id(
        {CCXT_PARAM_CLIENT_ORDER_ID: "echo-from-venue"},
        outbound_client_order_id="sent-outbound",
    )
    assert out == "echo-from-venue"


def test_resolve_falls_back_to_outbound_when_echo_missing() -> None:
    assert resolve_persisted_venue_client_order_id({}, outbound_client_order_id="pam-k-x") == "pam-k-x"


def test_resolve_returns_none_when_both_missing() -> None:
    assert resolve_persisted_venue_client_order_id({}, outbound_client_order_id=None) is None


def test_ensure_outbound_fallback_is_prefixed_unique_shape() -> None:
    a = ensure_outbound_ccxt_client_order_id(None)
    b = ensure_outbound_ccxt_client_order_id("")
    assert a.startswith(f"{CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX}-")
    assert b.startswith(f"{CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX}-")
    assert a != b
    assert len(a) <= CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN
