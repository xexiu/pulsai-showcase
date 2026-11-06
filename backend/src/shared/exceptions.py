"""
PulsAI Custom Exceptions — Source of Truth.

Structured exceptions for consistent error handling across the application.
All layers import from here (``src.shared.exceptions``).

``src.infrastructure.exceptions`` re-exports these symbols for backward
compatibility; new code should import from this module.

Usage::

    from src.shared.exceptions import (
        PulsAIException,
        ValidationError,
        AuthenticationError,
        NotFoundError,
        ConflictError,
        RateLimitError,
    )

    raise ValidationError(
        message="Password too weak",
        details={"min_length": 12, "provided_length": 8},
    )
"""

from src.shared.exception_types.base import (
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
    HTTP_UNPROCESSABLE_ENTITY,
    HTTP_VALIDATION_ERROR,
    PulsAIException,
)
from src.shared.exception_types.error_codes import ErrorCode
from src.shared.exception_types.http_errors import (
    AuthBackendUnavailableError,
    AuthenticationError,
    AutomationNotFoundError,
    CompoundV1LegMismatchError,
    CompoundV1LeverageMismatchError,
    CompoundV1NotionalMismatchError,
    ConflictError,
    DatabaseError,
    ExecutionLegIncompatibleError,
    ExternalServiceError,
    ForbiddenError,
    FullAutoTradingConsentRequiredError,
    IdempotencyKeyReuseError,
    NotFoundError,
    RateLimitError,
    ServicePausedError,
    UserNotFoundError,
    ValidationError,
)
from src.shared.exception_types.trading import (
    LiveTradingNotImplementedError,
    ModelLoadError,
    PaperCompoundCapExceededError,
    PaperCompoundDirectionError,
    PaperCompoundStepError,
    PaperFillResolutionError,
    PaperInsufficientMarginError,
    PaperOrderError,
    PaperSLTPPlacementError,
    PaperTradingPreflightError,
    TradingDomainError,
    VenueOrderError,
)
from src.shared.exception_types.training import TrainingCancelledError, TrainingPausedError

__all__ = [
    "HTTP_CLIENT_ERROR",
    "HTTP_CONFLICT",
    "HTTP_EXTERNAL_SERVICE_ERROR",
    "HTTP_FORBIDDEN",
    "HTTP_INTERNAL_ERROR",
    "HTTP_NOT_FOUND",
    "HTTP_RATE_LIMIT",
    "HTTP_SERVER_ERROR",
    "HTTP_SERVICE_UNAVAILABLE",
    "HTTP_UNAUTHORIZED",
    "HTTP_UNPROCESSABLE_ENTITY",
    "HTTP_VALIDATION_ERROR",
    "AuthBackendUnavailableError",
    "AuthenticationError",
    "AutomationNotFoundError",
    "CompoundV1LegMismatchError",
    "CompoundV1LeverageMismatchError",
    "CompoundV1NotionalMismatchError",
    "ConflictError",
    "DatabaseError",
    "ErrorCode",
    "ExecutionLegIncompatibleError",
    "ExternalServiceError",
    "ForbiddenError",
    "FullAutoTradingConsentRequiredError",
    "IdempotencyKeyReuseError",
    "LiveTradingNotImplementedError",
    "ModelLoadError",
    "NotFoundError",
    "PaperCompoundCapExceededError",
    "PaperCompoundDirectionError",
    "PaperCompoundStepError",
    "PaperFillResolutionError",
    "PaperInsufficientMarginError",
    "PaperOrderError",
    "PaperSLTPPlacementError",
    "PaperTradingPreflightError",
    "PulsAIException",
    "RateLimitError",
    "ServicePausedError",
    "TradingDomainError",
    "TrainingCancelledError",
    "TrainingPausedError",
    "UserNotFoundError",
    "ValidationError",
    "VenueOrderError",
]
