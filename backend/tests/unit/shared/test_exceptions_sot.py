"""
Verify shared/exceptions.py is the SoT for all PulsAI exception definitions.

Both import paths (shared and infrastructure) must expose identical symbols.
"""

from __future__ import annotations


def test_shared_exceptions_exports_all_classes() -> None:
    from src.shared.exceptions import (
        AuthenticationError,
        ConflictError,
        DatabaseError,
        ErrorCode,
        ExternalServiceError,
        ForbiddenError,
        ModelLoadError,
        NotFoundError,
        PulsAIException,
        RateLimitError,
        ServicePausedError,
        TradingDomainError,
        ValidationError,
    )

    assert issubclass(ValidationError, PulsAIException)
    assert issubclass(AuthenticationError, PulsAIException)
    assert issubclass(ForbiddenError, PulsAIException)
    assert issubclass(NotFoundError, PulsAIException)
    assert issubclass(ConflictError, PulsAIException)
    assert issubclass(RateLimitError, PulsAIException)
    assert issubclass(DatabaseError, PulsAIException)
    assert issubclass(ExternalServiceError, PulsAIException)
    assert issubclass(ServicePausedError, PulsAIException)
    assert issubclass(TradingDomainError, PulsAIException)
    assert issubclass(ModelLoadError, TradingDomainError)
    assert isinstance(ErrorCode.INTERNAL_ERROR, ErrorCode)


def test_shared_exceptions_exports_http_constants() -> None:
    from src.shared.exceptions import (
        HTTP_CLIENT_ERROR,
        HTTP_CONFLICT,
        HTTP_EXTERNAL_SERVICE_ERROR,
        HTTP_FORBIDDEN,
        HTTP_INTERNAL_ERROR,
        HTTP_NOT_FOUND,
        HTTP_RATE_LIMIT,
        HTTP_SERVER_ERROR,
        HTTP_SERVICE_UNAVAILABLE,
        HTTP_UNAUTHORIZED,
        HTTP_VALIDATION_ERROR,
    )

    assert HTTP_CLIENT_ERROR == 400
    assert HTTP_SERVER_ERROR == 500
    assert HTTP_NOT_FOUND == 404
    assert HTTP_VALIDATION_ERROR == 400
    assert HTTP_CONFLICT == 409
    assert HTTP_RATE_LIMIT == 429
    assert HTTP_INTERNAL_ERROR == 500
    assert HTTP_EXTERNAL_SERVICE_ERROR == 500
    assert HTTP_UNAUTHORIZED == 401
    assert HTTP_FORBIDDEN == 403
    assert HTTP_SERVICE_UNAVAILABLE == 503


def test_infrastructure_reexport_matches_shared() -> None:
    """infrastructure/exceptions.py must re-export the same symbols."""
    import src.infrastructure.exceptions as infra
    import src.shared.exceptions as shared

    shared_all = set(shared.__all__)
    for name in shared_all:
        assert hasattr(infra, name), f"{name} missing from infrastructure re-export"
        assert getattr(shared, name) is getattr(infra, name), f"{name} is not the same object in both modules"


def test_exception_behavior_validation_error() -> None:
    from src.shared.exceptions import ErrorCode, ValidationError

    err = ValidationError(message="bad input", details={"field": "email"})
    assert err.message == "bad input"
    assert err.code == ErrorCode.VALIDATION_ERROR
    assert err.status_code == 400
    assert err.details == {"field": "email"}
    d = err.to_dict()
    assert d["error"]["code"] == "VALIDATION_ERROR"
    assert d["error"]["message"] == "bad input"


def test_exception_behavior_rate_limit_with_retry() -> None:
    from src.shared.exceptions import RateLimitError

    err = RateLimitError(message="slow down", retry_after=60)
    assert err.status_code == 429
    assert err.details["retry_after"] == 60


def test_exception_behavior_service_paused() -> None:
    from src.shared.exceptions import ServicePausedError

    err = ServicePausedError(message="maintenance", feature="trading")
    assert err.status_code == 503
    assert err.details["feature"] == "trading"
