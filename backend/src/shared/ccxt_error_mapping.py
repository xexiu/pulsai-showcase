"""
Stable mapping from :mod:`ccxt` exceptions to PulsAI ``ErrorCode`` + safe messages (B6.8).

Why:
    Exchange adapters raise ``ccxt.BaseError`` subclasses whose messages include
    venue-specific, often-translated, sometimes noisy text (internal IDs, stack
    fragments, non-English strings). Forwarding that text to end users is:

    * a **UX regression** — the UI cannot i18n a free-form venue message;
    * a **leak vector** — venue IDs, endpoint paths, or customer identifiers can
      appear in the string;
    * a **contract hazard** — clients end up pattern-matching on substrings that
      change without warning between CCXT releases.

    This module provides a single pure function :func:`map_ccxt_error` that
    converts a ``ccxt.BaseError`` to a deterministic ``(ErrorCode, safe_message)``
    pair. Callers log the raw ``ccxt`` message server-side and surface the safe
    message + code to the client.

Scope:
    Pure function. No I/O, no logging, no exception raising. Callers decide what
    to raise (typically :class:`src.shared.exceptions.VenueOrderError`).
"""

from __future__ import annotations

import logging
from typing import Final, NoReturn

import ccxt.async_support as ccxt

from src.shared.exceptions import ErrorCode, VenueOrderError

# Re-export ccxt exception classes as SoT aliases so callers outside
# ``infrastructure/`` can write ``except CcxtBaseError`` (or the more specific
# ``CcxtNotSupported``) without taking a runtime ``import ccxt`` themselves
# -- enforced by ``tests/unit/architecture/test_no_ccxt_import_outside_infrastructure.py``.
# This module is one of the three documented allowlist exceptions because it
# IS the SoT mapping CCXT exception types -> ErrorCode; it cannot itself obey
# the rule without circularity.
CcxtBaseError = ccxt.BaseError
CcxtNotSupported = ccxt.NotSupported
CcxtExchange = ccxt.Exchange  # type alias for code that previously took ``ccxt.Exchange``
# Specific exception aliases so worker/task code outside ``infrastructure/`` can catch or
# classify them without a direct ``import ccxt`` (same architecture-test seam as above).
CcxtInsufficientFunds = ccxt.InsufficientFunds
CcxtNetworkError = ccxt.NetworkError
CcxtExchangeNotAvailable = ccxt.ExchangeNotAvailable
CcxtRequestTimeout = ccxt.RequestTimeout
CcxtDDoSProtection = ccxt.DDoSProtection

__all__ = [
    "CCXT_FALLBACK_MESSAGE",
    "CCXT_VENUE_OP_CANCEL_ORDER",
    "CCXT_VENUE_OP_PLACE_LIMIT_ORDER",
    "CCXT_VENUE_OP_PLACE_MARKET_ORDER",
    "CcxtBaseError",
    "CcxtDDoSProtection",
    "CcxtExchange",
    "CcxtExchangeNotAvailable",
    "CcxtInsufficientFunds",
    "CcxtNetworkError",
    "CcxtNotSupported",
    "CcxtRequestTimeout",
    "log_and_raise_venue_error",
    "map_ccxt_error",
]

# SoT: ``operation`` labels for :func:`log_and_raise_venue_error` (logging + extras).
# Keep stable — dashboards or log parsers may key on these strings.
CCXT_VENUE_OP_PLACE_MARKET_ORDER: Final[str] = "place_market_order"
CCXT_VENUE_OP_PLACE_LIMIT_ORDER: Final[str] = "place_limit_order"
CCXT_VENUE_OP_CANCEL_ORDER: Final[str] = "cancel_order"

logger = logging.getLogger(__name__)


CCXT_FALLBACK_MESSAGE = "Exchange returned an unexpected error. Please retry in a moment."


_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.CCXT_INSUFFICIENT_FUNDS: "Insufficient balance on the exchange to place this order.",
    ErrorCode.CCXT_INVALID_ORDER: "The exchange rejected the order parameters. Review amount, price, and symbol precision.",
    ErrorCode.CCXT_BAD_SYMBOL: "The exchange does not list this symbol.",
    ErrorCode.CCXT_RATE_LIMITED: "The exchange is rate-limiting requests. Please retry shortly.",
    ErrorCode.CCXT_AUTH_FAILED: "The exchange rejected the API credentials. Reconnect the exchange in Settings.",
    ErrorCode.CCXT_EXCHANGE_UNAVAILABLE: "The exchange is temporarily unavailable. Please retry shortly.",
    ErrorCode.CCXT_NETWORK_ERROR: "Network error talking to the exchange. Please retry shortly.",
    ErrorCode.CCXT_UNKNOWN: CCXT_FALLBACK_MESSAGE,
}


def map_ccxt_error(exc: ccxt.BaseError) -> tuple[ErrorCode, str]:
    """Translate a CCXT exception into a stable code + safe user-facing message.

    Order matters: most-specific exception types are checked first so subclasses
    like :class:`ccxt.InvalidOrder` (which inherits from :class:`ccxt.ExchangeError`)
    are not collapsed into their parent's bucket.

    Args:
        exc: The exception raised by a CCXT call.

    Returns:
        ``(ErrorCode, safe_message)``. The safe message is short, i18n-friendly,
        and never includes raw venue text.
    """
    code = _classify(exc)
    return code, _MESSAGES[code]


def log_and_raise_venue_error(exc: ccxt.BaseError, *, operation: str) -> NoReturn:
    """Log raw CCXT text server-side, then raise a safe ``VenueOrderError``.

    Call from any venue-adjacent code path that catches ``ccxt.BaseError`` and
    needs to surface a stable ``ErrorCode`` to clients without forwarding
    venue-specific strings. The raw ``exc`` is kept **only** in the server log
    (with exception type + operation context) and replaced by a deterministic,
    i18n-ready safe message in the exception that propagates.
    """
    code, safe_message = map_ccxt_error(exc)
    logger.warning(
        "CCXT %s failed (%s): %s",
        operation,
        type(exc).__name__,
        exc,
        extra={"ccxt_error_code": code.value, "operation": operation},
    )
    raise VenueOrderError(code=code, message=safe_message) from exc


def _classify(exc: ccxt.BaseError) -> ErrorCode:
    if isinstance(exc, ccxt.InsufficientFunds):
        return ErrorCode.CCXT_INSUFFICIENT_FUNDS
    if isinstance(exc, ccxt.BadSymbol):
        return ErrorCode.CCXT_BAD_SYMBOL
    if isinstance(exc, ccxt.InvalidOrder):
        return ErrorCode.CCXT_INVALID_ORDER
    if isinstance(exc, ccxt.AuthenticationError):
        return ErrorCode.CCXT_AUTH_FAILED
    if isinstance(exc, ccxt.RateLimitExceeded):
        return ErrorCode.CCXT_RATE_LIMITED
    if isinstance(exc, ccxt.ExchangeNotAvailable):
        return ErrorCode.CCXT_EXCHANGE_UNAVAILABLE
    if isinstance(exc, ccxt.NetworkError):
        return ErrorCode.CCXT_NETWORK_ERROR
    return ErrorCode.CCXT_UNKNOWN
