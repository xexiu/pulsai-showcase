"""Boundary translator: exchange service ``ValueError`` → typed :class:`PulsAIException`.

Mirrors :mod:`src.api.v1.endpoints._trading_value_error_mapping` for the
``/exchanges`` router so clients receive stable ``ErrorCode`` values instead of
raw English passthrough strings.
"""

from __future__ import annotations

from src.shared.constants.exchanges import (
    CONNECTION_DISCONNECTED_RECONNECT_DETAIL,
    EXCHANGE_KEY_TESTNET_AUTH_FAILED_PREFIX,
    EXCHANGE_NOT_SUPPORTED_DETAIL_PREFIX,
    EXCHANGE_VERIFICATION_FAILED_PREFIX,
    EXCHANGE_VERIFY_FAILED_PREFIX,
)
from src.shared.constants.paper_trading import CONNECTION_NOT_FOUND_DETAIL
from src.shared.exceptions import (
    ErrorCode,
    NotFoundError,
    PulsAIException,
    ValidationError,
)


def _is_exchange_verification_failure(detail: str) -> bool:
    return detail.startswith(
        (
            EXCHANGE_KEY_TESTNET_AUTH_FAILED_PREFIX,
            EXCHANGE_VERIFICATION_FAILED_PREFIX,
            EXCHANGE_VERIFY_FAILED_PREFIX,
        ),
    )


def translate_exchange_value_error(exc: ValueError) -> PulsAIException:
    """Map a service-level ``ValueError`` into the typed HTTP envelope."""
    detail = str(exc)

    if detail == CONNECTION_NOT_FOUND_DETAIL:
        translated: PulsAIException = NotFoundError(
            message=detail,
            code=ErrorCode.CONNECTION_NOT_FOUND,
        )
    elif detail == CONNECTION_DISCONNECTED_RECONNECT_DETAIL:
        translated = ValidationError(
            message=detail,
            code=ErrorCode.CONNECTION_NOT_ACTIVE,
        )
    elif detail.startswith(EXCHANGE_NOT_SUPPORTED_DETAIL_PREFIX):
        translated = ValidationError(
            message=detail,
            code=ErrorCode.INVALID_PARAMETER,
        )
    elif _is_exchange_verification_failure(detail):
        translated = ValidationError(message=detail)
    else:
        translated = ValidationError(message=detail)

    translated.__cause__ = exc
    return translated
