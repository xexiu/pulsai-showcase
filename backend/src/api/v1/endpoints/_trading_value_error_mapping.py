"""Boundary translator: service ``ValueError`` → typed :class:`PulsAIException`.

Why this module exists
----------------------

P3-MED-5 of the Phase 3 audit flagged that the trading router was catching
``ValueError`` from the service layer and re-surfacing it with
``raise HTTPException(status_code=400, detail=str(exc))``. That passthrough
defeats internationalisation: the frontend only has localised strings for
*known* error codes (see ``apps/web/src/lib/trading-place-order-error.ts``),
so a user on the Spanish bundle would be shown the English service message
``"Live trading is not enabled."`` verbatim.

This module centralises the boundary mapping so the HTTP layer emits a stable
``ErrorCode`` (``LIVE_TRADING_NOT_ENABLED``, ``CONNECTION_NOT_FOUND``, …). The
FE keys its translation bundle off that code, keeping en/es copy under its
sole ownership.

Design constraints
------------------

* **No service changes.** We keep the services raising plain ``ValueError``
  with the shared detail constants from :mod:`src.shared.constants.paper_trading`
  so domain/unit tests that assert ``str(exc) == DETAIL`` keep passing. The
  boundary is the *only* place that elevates those strings into codes.
* **Unknown messages fall back to a generic ``VALIDATION_ERROR``.** That
  matches the previous HTTP 400 behaviour and does NOT claim an i18n code we
  don't have bundle coverage for — a parity test on the FE asserts each code
  has en+es entries.
* **``__cause__`` preserved.** Sentry still sees the original service-level
  stack frame for observability; we only reshape the outward-facing envelope.
"""

from __future__ import annotations

from src.shared.constants.paper_trading import (
    CONNECTION_DISCONNECTED_DETAIL,
    CONNECTION_NOT_ACTIVE_DETAIL,
    CONNECTION_NOT_FOUND_DETAIL,
    LIVE_NOT_ENABLED_DETAIL,
    LIVE_REQUIRES_MAINNET_CONNECTION_DETAIL,
)
from src.shared.constants.spot_bracket_errors import (
    SPOT_BRACKET_NOT_IMPLEMENTED,
    SPOT_BRACKET_SPOT_SELL_BRACKET,
    SPOT_BRACKET_UNSUPPORTED_VENUE,
)
from src.shared.exceptions import (
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    PulsAIException,
    ValidationError,
)


def translate_trading_value_error(exc: ValueError) -> PulsAIException:
    """Map a service-level ``ValueError`` into the typed HTTP envelope.

    The returned exception is ready to ``raise ... from exc``; callers MUST
    chain the original ``ValueError`` so log/Sentry context is preserved.
    """
    detail = str(exc)

    if detail == LIVE_NOT_ENABLED_DETAIL:
        translated: PulsAIException = ForbiddenError(
            message=detail,
            code=ErrorCode.LIVE_TRADING_NOT_ENABLED,
        )
    elif detail == LIVE_REQUIRES_MAINNET_CONNECTION_DETAIL:
        translated = ValidationError(
            message=detail,
            code=ErrorCode.LIVE_TRADING_REQUIRES_MAINNET,
        )
    elif detail == CONNECTION_NOT_FOUND_DETAIL:
        translated = NotFoundError(
            message=detail,
            code=ErrorCode.CONNECTION_NOT_FOUND,
        )
    elif detail in {CONNECTION_NOT_ACTIVE_DETAIL, CONNECTION_DISCONNECTED_DETAIL}:
        translated = ValidationError(
            message=detail,
            code=ErrorCode.CONNECTION_NOT_ACTIVE,
        )
    elif detail == SPOT_BRACKET_UNSUPPORTED_VENUE:
        translated = ValidationError(
            message=detail,
            code=ErrorCode.SPOT_BRACKET_UNSUPPORTED_VENUE,
        )
    elif detail == SPOT_BRACKET_NOT_IMPLEMENTED:
        translated = ValidationError(
            message=detail,
            code=ErrorCode.SPOT_BRACKET_NOT_IMPLEMENTED,
        )
    elif detail == SPOT_BRACKET_SPOT_SELL_BRACKET:
        translated = ValidationError(
            message=detail,
            code=ErrorCode.SPOT_BRACKET_SPOT_SELL_BRACKET,
        )
    else:
        translated = ValidationError(message=detail)

    translated.__cause__ = exc
    return translated
