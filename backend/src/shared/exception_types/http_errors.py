"""HTTP-mapped API exceptions: 4xx/5xx/503 and 422 business-rule errors (re-exported by ``src.shared.exceptions``)."""

from typing import Any

from src.shared.exception_types.base import (
    HTTP_CLIENT_ERROR,
    HTTP_CONFLICT,
    HTTP_EXTERNAL_SERVICE_ERROR,
    HTTP_FORBIDDEN,
    HTTP_INTERNAL_ERROR,
    HTTP_NOT_FOUND,
    HTTP_RATE_LIMIT,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_UNAUTHORIZED,
    HTTP_UNPROCESSABLE_ENTITY,
    PulsAIException,
)
from src.shared.exception_types.error_codes import ErrorCode


class ValidationError(PulsAIException):
    """Validation error (400).

    P3-MED-5: accepts an optional ``code`` override so routers can emit stable,
    locale-aware rejections (``FUTURES_NOT_ENABLED``, ``CONNECTION_NOT_ACTIVE``,
    ...) instead of passing raw English ``ValueError`` messages straight to the
    frontend. ``code`` defaults to :attr:`ErrorCode.VALIDATION_ERROR` to keep
    every existing caller behaving unchanged.
    """

    def __init__(
        self,
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
        code: ErrorCode = ErrorCode.VALIDATION_ERROR,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=HTTP_CLIENT_ERROR,
            details=details,
        )


class ExecutionLegIncompatibleError(PulsAIException):
    """422 when execution_leg_mode cannot apply to the strategy snapshot type."""

    def __init__(
        self,
        *,
        strategy_type: str,
        attempted_mode: str,
        message: str = "Execution leg mode is incompatible with the strategy snapshot.",
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.EXECUTION_LEG_INCOMPATIBLE_WITH_SNAPSHOT,
            status_code=HTTP_UNPROCESSABLE_ENTITY,
            details={
                "strategy_type": strategy_type,
                "attempted_mode": attempted_mode,
            },
        )


class FullAutoTradingConsentRequiredError(PulsAIException):
    """422 when user enables ``full_auto`` without prior ADR-009 consent."""

    def __init__(
        self,
        message: str = "Full auto trading requires explicit consent. Use POST /api/v1/auth/me/full-auto-trading-consent.",
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.FULL_AUTO_TRADING_CONSENT_REQUIRED,
            status_code=HTTP_UNPROCESSABLE_ENTITY,
            details={},
        )


class CompoundV1LegMismatchError(PulsAIException):
    """422 parent for compound/DCA leg invariants.

    Kept as a catchable base class so callers doing
    ``except CompoundV1LegMismatchError`` continue to work after the error
    code split. New raise sites MUST use one of the two concrete subclasses
    below so the emitted ``ErrorCode`` is specific; raising this parent
    directly is allowed only for exceptional cases that fit neither
    specialization (none exist today).
    """

    def __init__(
        self,
        *,
        message: str,
        details: dict[str, Any] | None = None,
        code: ErrorCode = ErrorCode.COMPOUND_V1_LEG_MISMATCH,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=HTTP_UNPROCESSABLE_ENTITY,
            details=details or {},
        )


class CompoundV1LeverageMismatchError(CompoundV1LegMismatchError):
    """422 when a swap compound leg's leverage differs from the anchor leg.

    ``details`` always carries ``anchor_leverage`` + ``incoming_leverage``
    so callers can render a specific message or auto-retry at the anchor's
    leverage without string-parsing.
    """

    def __init__(
        self,
        *,
        anchor_leverage: int | None,
        incoming_leverage: int | None,
        message: str = "Compound futures leg must use the same leverage as the anchor leg.",
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.COMPOUND_V1_LEVERAGE_MISMATCH,
            details={
                "anchor_leverage": anchor_leverage,
                "incoming_leverage": incoming_leverage,
            },
        )


class CompoundV1NotionalMismatchError(CompoundV1LegMismatchError):
    """422 when a compound leg's quote notional cannot be shown to match the anchor.

    Covers three concrete failure modes that share the same contract
    semantics ("leg cannot prove notional matches anchor"):

    * drift beyond the 2% relative tolerance,
    * missing / non-positive reference price,
    * non-positive incoming notional.

    ``details`` surfaces whatever values are available at the raise site so
    the FE can render "anchor $600 → leg $700 (+16.6%)" without re-parsing
    the human-readable message.
    """

    def __init__(
        self,
        *,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.COMPOUND_V1_NOTIONAL_MISMATCH,
            details=details or {},
        )


class AuthenticationError(PulsAIException):
    """Authentication error (401)."""

    def __init__(
        self,
        message: str = "Authentication required",
        code: ErrorCode = ErrorCode.UNAUTHORIZED,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=HTTP_UNAUTHORIZED,
            details=details,
        )


class ForbiddenError(PulsAIException):
    """Forbidden error (403) — user authenticated but lacks permission."""

    def __init__(
        self,
        message: str = "Permission denied",
        code: ErrorCode = ErrorCode.FORBIDDEN,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=HTTP_FORBIDDEN,
            details=details,
        )


class NotFoundError(PulsAIException):
    """Resource not found error (404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: ErrorCode = ErrorCode.NOT_FOUND,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=HTTP_NOT_FOUND,
            details=details,
        )


class UserNotFoundError(NotFoundError):
    """Typed 404 when a user aggregate cannot be resolved.

    Phase 9 Track B: the automation-executor orchestrator branches on
    ``except UserNotFoundError`` instead of substring-matching
    ``exc.message`` so the metrics label (``user_not_found``) is typed
    end-to-end. Existing ``except NotFoundError`` handlers keep working
    because this is a subclass.
    """

    def __init__(
        self,
        message: str = "User not found.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.USER_NOT_FOUND,
            details=details,
        )


class AutomationNotFoundError(NotFoundError):
    """Typed 404 when a trading-automation row cannot be resolved.

    Phase 9 Track B counterpart to :class:`UserNotFoundError`; keeps the
    orchestrator free of ``"Automation not found" in exc.message`` string
    checks. ``code=ErrorCode.NOT_FOUND`` preserves the existing API
    contract (we don't introduce a new public code for the auto path).
    """

    def __init__(
        self,
        message: str = "Automation not found.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND,
            details=details,
        )


class ConflictError(PulsAIException):
    """Conflict error (409)."""

    def __init__(
        self,
        message: str = "Resource already exists",
        code: ErrorCode = ErrorCode.CONFLICT,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=HTTP_CONFLICT,
            details=details,
        )


class IdempotencyKeyReuseError(ConflictError):
    """409 when the same Idempotency-Key is reused for a different operation or scope."""

    def __init__(
        self,
        message: str = "Idempotency-Key was already used for a different operation.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.IDEMPOTENCY_KEY_REUSE,
            details=details,
        )


class RateLimitError(PulsAIException):
    """Rate limit exceeded error (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if retry_after:
            _details["retry_after"] = retry_after
        super().__init__(
            message=message,
            code=ErrorCode.RATE_LIMITED,
            status_code=HTTP_RATE_LIMIT,
            details=_details,
        )


class DatabaseError(PulsAIException):
    """Database operation error (500)."""

    def __init__(
        self,
        message: str = "Database operation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.DATABASE_ERROR,
            status_code=HTTP_INTERNAL_ERROR,
            details=details,
        )


class ExternalServiceError(PulsAIException):
    """External service error (500)."""

    def __init__(
        self,
        message: str = "External service unavailable",
        service: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        _details = details or {}
        if service:
            _details["service"] = service
        super().__init__(
            message=message,
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            status_code=HTTP_EXTERNAL_SERVICE_ERROR,
            details=_details,
        )


class ServicePausedError(PulsAIException):
    """
    Feature temporarily disabled by operators (503).

    WHY 503: Clients should treat this as temporary unavailability, not a client bug.
    """

    def __init__(
        self,
        message: str,
        *,
        feature: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = {"feature": feature}
        if details:
            merged.update(details)
        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_PAUSED,
            status_code=HTTP_SERVICE_UNAVAILABLE,
            details=merged,
        )


class AuthBackendUnavailableError(AuthenticationError):
    """The token-revocation backend is unreachable, so the request is denied (503).

    SUBCLASSES AuthenticationError DELIBERATELY. Two callers catch that type and depend on it:
    `get_optional_user` swallows it to fall back to anonymous, and the WebSocket handler closes
    with 1008 "Authentication required". A sibling class would escape both — turning an
    optional-auth page into a 503 during a blip it was designed to shrug off, and sending the
    socket down the generic `except Exception` path. Same catch behaviour, different answer.

    STILL FAIL-CLOSED. If we cannot ask whether a token was revoked, honouring it would let a
    revoked token through, which defeats logout and ban. The request is denied either way; only
    the SIGNAL changes.

    WHY NOT 401, which is what this used to raise. A 401 means "your credentials are not good".
    The browser client acts on exactly that: `maybeHandleUnauthorizedResponse` sees 401, tries a
    refresh, and calls `handleSessionExpired()` when the refresh also fails -- and during a Redis
    outage the refresh path hits the SAME blacklist check, so it fails too. Net effect: a few
    seconds of Redis trouble signs out every active user, and each of them has to log in again.

    A 503 says "try again shortly", which is true, and the client's sign-out path is keyed to 401,
    so the session survives an outage it was never evidence against. Same denial, no collateral.
    """

    def __init__(
        self,
        message: str = "Authentication backend unavailable",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.AUTH_BACKEND_UNAVAILABLE,
            details=details or {},
        )
        # `AuthenticationError.__init__` hardcodes 401 for every subclass. Reassigning after the
        # super call is what lets this stay inside that catch hierarchy while still answering 503.
        self.status_code = HTTP_SERVICE_UNAVAILABLE
