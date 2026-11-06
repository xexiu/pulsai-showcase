"""HTTP status constants and the ``PulsAIException`` base (re-exported by ``src.shared.exceptions``)."""

from typing import Any

from src.shared.exception_types.error_codes import ErrorCode

# ---------------------------------------------------------------------------
# HTTP status classification (SoT for server vs client error thresholds)
# ---------------------------------------------------------------------------
HTTP_CLIENT_ERROR = 400
HTTP_SERVER_ERROR = 500
HTTP_NOT_FOUND = 404
HTTP_VALIDATION_ERROR = 400
HTTP_CONFLICT = 409
HTTP_RATE_LIMIT = 429
HTTP_INTERNAL_ERROR = 500
HTTP_EXTERNAL_SERVICE_ERROR = 500
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_UNPROCESSABLE_ENTITY = 422


class PulsAIException(Exception):
    """
    Base exception for all PulsAI application errors.

    Attributes:
        message: Human-readable error message.
        code: ErrorCode enum value.
        status_code: HTTP status code.
        details: Optional additional context.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = HTTP_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to API error response format."""
        error_data: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            error_data["details"] = self.details
        return {"error": error_data}
