"""Unit tests for :mod:`src.api.v1.endpoints._exchange_value_error_mapping`.

Exchange routers previously surfaced raw ``ValueError`` strings via
``HTTPException(detail=str(exc))``, defeating i18n and stable ``ErrorCode``
contracts. This suite locks the boundary translator.
"""

from __future__ import annotations

import pytest

from src.api.v1.endpoints._exchange_value_error_mapping import (
    translate_exchange_value_error,
)
from src.shared.constants.exchanges import (
    CONNECTION_DISCONNECTED_RECONNECT_DETAIL,
    EXCHANGE_KEY_TESTNET_AUTH_FAILED_PREFIX,
    exchange_not_supported_detail,
)
from src.shared.constants.paper_trading import CONNECTION_NOT_FOUND_DETAIL
from src.shared.exceptions import (
    ErrorCode,
    NotFoundError,
    PulsAIException,
    ValidationError,
)


def _assert_exact(
    exc: PulsAIException,
    expected_type: type[PulsAIException],
    code: ErrorCode,
    message: str,
) -> None:
    assert type(exc) is expected_type
    assert exc.code is code
    assert exc.message == message


class TestTranslateExchangeValueError:
    def test_connection_not_found_maps_to_not_found(self) -> None:
        exc = translate_exchange_value_error(ValueError(CONNECTION_NOT_FOUND_DETAIL))
        _assert_exact(
            exc,
            NotFoundError,
            ErrorCode.CONNECTION_NOT_FOUND,
            CONNECTION_NOT_FOUND_DETAIL,
        )

    def test_disconnected_reconnect_maps_to_connection_not_active(self) -> None:
        exc = translate_exchange_value_error(
            ValueError(CONNECTION_DISCONNECTED_RECONNECT_DETAIL),
        )
        _assert_exact(
            exc,
            ValidationError,
            ErrorCode.CONNECTION_NOT_ACTIVE,
            CONNECTION_DISCONNECTED_RECONNECT_DETAIL,
        )

    def test_unsupported_exchange_maps_to_invalid_parameter(self) -> None:
        detail = exchange_not_supported_detail("fakecoin")
        exc = translate_exchange_value_error(ValueError(detail))
        _assert_exact(
            exc,
            ValidationError,
            ErrorCode.INVALID_PARAMETER,
            detail,
        )

    @pytest.mark.parametrize(
        "detail",
        [
            f"{EXCHANGE_KEY_TESTNET_AUTH_FAILED_PREFIX} binance testnet/sandbox.",
            "Exchange verification failed: timeout",
            "Verification failed: invalid key",
        ],
    )
    def test_exchange_verification_failures_map_to_validation_error(self, detail: str) -> None:
        exc = translate_exchange_value_error(ValueError(detail))
        _assert_exact(exc, ValidationError, ErrorCode.VALIDATION_ERROR, detail)

    def test_unknown_value_error_falls_back_to_generic_validation_error(self) -> None:
        detail = "unexpected exchange lifecycle rejection"
        exc = translate_exchange_value_error(ValueError(detail))
        _assert_exact(exc, ValidationError, ErrorCode.VALIDATION_ERROR, detail)

    def test_preserves_exception_as_cause_for_observability(self) -> None:
        original = ValueError(CONNECTION_NOT_FOUND_DETAIL)
        exc = translate_exchange_value_error(original)
        assert exc.__cause__ is original
