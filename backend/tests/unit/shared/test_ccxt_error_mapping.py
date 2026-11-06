"""
Unit tests for :mod:`src.shared.ccxt_error_mapping`.

B6.8 contract:
    Every ``ccxt.BaseError`` subclass raised by an exchange adapter MUST be
    translated to a stable ``ErrorCode`` and a **safe, short, internationalizable
    message**. The raw CCXT message (which may contain venue-specific identifiers,
    translated fragments, or upstream trace data) is logged server-side but
    never forwarded to the client.
"""

from __future__ import annotations

import ccxt.async_support as ccxt
import pytest

from src.shared.ccxt_error_mapping import (
    CCXT_FALLBACK_MESSAGE,
    CCXT_VENUE_OP_CANCEL_ORDER,
    log_and_raise_venue_error,
    map_ccxt_error,
)
from src.shared.exceptions import ErrorCode, VenueOrderError


@pytest.mark.parametrize(
    ("exc_cls", "expected_code"),
    [
        (ccxt.InsufficientFunds, ErrorCode.CCXT_INSUFFICIENT_FUNDS),
        (ccxt.InvalidOrder, ErrorCode.CCXT_INVALID_ORDER),
        (ccxt.BadSymbol, ErrorCode.CCXT_BAD_SYMBOL),
        (ccxt.RateLimitExceeded, ErrorCode.CCXT_RATE_LIMITED),
        (ccxt.AuthenticationError, ErrorCode.CCXT_AUTH_FAILED),
        (ccxt.ExchangeNotAvailable, ErrorCode.CCXT_EXCHANGE_UNAVAILABLE),
        (ccxt.NetworkError, ErrorCode.CCXT_NETWORK_ERROR),
    ],
)
def test_map_ccxt_error_returns_stable_code_per_exception_type(
    exc_cls: type[ccxt.BaseError],
    expected_code: ErrorCode,
) -> None:
    """Each known CCXT exception class maps to a deterministic PulsAI code."""
    code, message = map_ccxt_error(exc_cls("venue said something internal"))
    assert code is expected_code
    assert message
    assert "venue said something internal" not in message


def test_map_ccxt_error_falls_back_for_unknown_base_error() -> None:
    """An unspecialized ``ccxt.BaseError`` maps to the safe fallback code + message.

    Rationale: rather than leak unknown venue text to the client, use one
    conservative fallback so the UI can show a generic "try again" and SRE
    can investigate via server logs.
    """
    code, message = map_ccxt_error(ccxt.BaseError("some raw venue trace"))
    assert code is ErrorCode.CCXT_UNKNOWN
    assert message == CCXT_FALLBACK_MESSAGE
    assert "raw venue trace" not in message


def test_map_ccxt_error_never_returns_empty_message() -> None:
    """Guard against an empty ``exc.args`` causing an empty user-facing string."""
    code, message = map_ccxt_error(ccxt.InsufficientFunds())
    assert code is ErrorCode.CCXT_INSUFFICIENT_FUNDS
    assert message.strip()


def test_map_ccxt_error_specific_subclass_wins_over_parent() -> None:
    """``InvalidOrder`` inherits from ``ExchangeError``; the mapper must not
    collapse it to the parent's generic bucket.
    """
    code, _ = map_ccxt_error(ccxt.InvalidOrder("price out of range"))
    assert code is ErrorCode.CCXT_INVALID_ORDER


def test_log_and_raise_venue_error_translates_and_preserves_cause(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The raw CCXT text is logged server-side but never reaches the exception message."""
    original = ccxt.InsufficientFunds("balance too low: 0.00001 BTC on acct-999")

    with caplog.at_level("WARNING"), pytest.raises(VenueOrderError) as info:
        log_and_raise_venue_error(original, operation="place_limit")

    assert info.value.code == ErrorCode.CCXT_INSUFFICIENT_FUNDS
    assert "acct-999" not in info.value.message
    assert info.value.__cause__ is original
    assert any("place_limit" in rec.message for rec in caplog.records)
    assert any("acct-999" in rec.message for rec in caplog.records)


def test_log_and_raise_venue_error_rejects_non_ccxt_errors_via_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown base errors still translate — never let raw exception text leak."""
    with caplog.at_level("WARNING"), pytest.raises(VenueOrderError) as info:
        log_and_raise_venue_error(
            ccxt.BaseError("mystery trace"),
            operation=CCXT_VENUE_OP_CANCEL_ORDER,
        )

    assert info.value.code == ErrorCode.CCXT_UNKNOWN
    assert "mystery trace" not in info.value.message
