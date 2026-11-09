"""Unit tests for :mod:`src.api.v1.endpoints._trading_value_error_mapping`.

P3-MED-5 bilingual gap closure — the trading router used to surface raw
``ValueError(msg)`` strings to the frontend via ``HTTPException(detail=str(exc))``.
That passthrough defeats i18n because the FE only has a translation bundle for
*known* error codes, so a Spanish user would see English strings like
``"Live trading is not enabled."``.

This test suite locks the behaviour that a well-known service rejection
message is translated at the router boundary into a typed
:class:`PulsAIException` carrying a stable ``ErrorCode`` that the FE can map to
a localised string. We purposely do not test the service layer here — only the
mapping table and fallback semantics.
"""

from __future__ import annotations

import pytest

from src.api.v1.endpoints._trading_value_error_mapping import (
    translate_trading_value_error,
)
from src.shared.constants.paper_trading import (
    CONNECTION_DISCONNECTED_DETAIL,
    CONNECTION_NOT_ACTIVE_DETAIL,
    CONNECTION_NOT_FOUND_DETAIL,
    LIVE_NOT_ENABLED_DETAIL,
    LIVE_REQUIRES_MAINNET_CONNECTION_DETAIL,
)
from src.shared.exceptions import (
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    PulsAIException,
    ValidationError,
)


def _assert_exact(exc: PulsAIException, expected_type: type[PulsAIException], code: ErrorCode, message: str) -> None:
    assert type(exc) is expected_type, f"translate_trading_value_error returned {type(exc).__name__}, expected {expected_type.__name__}"
    assert exc.code is code, f"expected code={code!r}, got {exc.code!r}"
    assert exc.message == message, f"expected message={message!r}, got {exc.message!r}"


class TestTranslateTradingValueError:
    """``translate_trading_value_error(exc)`` is a pure dispatcher keyed on the
    raw detail string. It MUST be exhaustive for the messages we currently
    raise from services the trading router is allowed to surface, and MUST
    fall back to a generic ``ValidationError`` for unknown messages (no
    ``ErrorCode`` change) so we do not silently claim i18n support we didn't
    add to the bundles yet.
    """

    def test_live_not_enabled_maps_to_forbidden_with_stable_code(self) -> None:
        exc = translate_trading_value_error(ValueError(LIVE_NOT_ENABLED_DETAIL))
        _assert_exact(
            exc,
            ForbiddenError,
            ErrorCode.LIVE_TRADING_NOT_ENABLED,
            LIVE_NOT_ENABLED_DETAIL,
        )

    def test_live_requires_mainnet_maps_to_validation_with_stable_code(self) -> None:
        exc = translate_trading_value_error(
            ValueError(LIVE_REQUIRES_MAINNET_CONNECTION_DETAIL),
        )
        _assert_exact(
            exc,
            ValidationError,
            ErrorCode.LIVE_TRADING_REQUIRES_MAINNET,
            LIVE_REQUIRES_MAINNET_CONNECTION_DETAIL,
        )

    def test_connection_not_found_maps_to_not_found(self) -> None:
        exc = translate_trading_value_error(ValueError(CONNECTION_NOT_FOUND_DETAIL))
        _assert_exact(
            exc,
            NotFoundError,
            ErrorCode.CONNECTION_NOT_FOUND,
            CONNECTION_NOT_FOUND_DETAIL,
        )

    @pytest.mark.parametrize(
        "detail",
        [CONNECTION_NOT_ACTIVE_DETAIL, CONNECTION_DISCONNECTED_DETAIL],
    )
    def test_connection_not_active_variants_map_to_validation(
        self,
        detail: str,
    ) -> None:
        exc = translate_trading_value_error(ValueError(detail))
        _assert_exact(
            exc,
            ValidationError,
            ErrorCode.CONNECTION_NOT_ACTIVE,
            detail,
        )

    def test_unknown_value_error_falls_back_to_generic_validation_error(self) -> None:
        detail = "arbitrary backend rejection we haven't localised yet"
        exc = translate_trading_value_error(ValueError(detail))
        _assert_exact(
            exc,
            ValidationError,
            ErrorCode.VALIDATION_ERROR,
            detail,
        )

    def test_empty_value_error_message_still_returns_validation_error(self) -> None:
        exc = translate_trading_value_error(ValueError(""))
        assert isinstance(exc, ValidationError)
        assert exc.code is ErrorCode.VALIDATION_ERROR

    def test_preserves_exception_as_cause_for_observability(self) -> None:
        original = ValueError(LIVE_NOT_ENABLED_DETAIL)
        exc = translate_trading_value_error(original)
        assert exc.__cause__ is original, (
            "Boundary translator must preserve the originating ValueError as __cause__ so Sentry/log traces still show the service-level stack."
        )
