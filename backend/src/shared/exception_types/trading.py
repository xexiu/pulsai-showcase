"""Trading / ML / paper-order exceptions (re-exported by ``src.shared.exceptions``)."""

from typing import Any

from src.shared.constants.paper_trading import ORDER_SIDE_BUY
from src.shared.exception_types.base import (
    HTTP_CLIENT_ERROR,
    HTTP_RATE_LIMIT,
    HTTP_SERVER_ERROR,
    HTTP_SERVICE_UNAVAILABLE,
    PulsAIException,
)
from src.shared.exception_types.error_codes import ErrorCode


class TradingDomainError(PulsAIException):
    """Base for trading / ML domain errors (maps to 500 unless subclass specifies)."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.INTERNAL_ERROR,
            status_code=HTTP_SERVER_ERROR,
            details=details,
        )


class ModelLoadError(TradingDomainError):
    """Raised when production or candidate models cannot be loaded from storage."""

    def __init__(
        self,
        message: str = "Failed to load ML model",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)


# ---------------------------------------------------------------------------
# Paper trading exceptions
# ---------------------------------------------------------------------------


class LiveTradingNotImplementedError(RuntimeError):
    """Raised when mode=live is requested before the live trading epic ships."""


class PaperOrderError(TradingDomainError):
    """Base for paper (CCXT sandbox) order errors."""

    def __init__(
        self,
        message: str = "Paper order operation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)


class PaperFillResolutionError(PaperOrderError):
    """Fill data could not be resolved after max retries."""

    def __init__(
        self,
        paper_order_id: str,
        message: str = "Fill resolution failed after max retries",
        details: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = {"paper_order_id": paper_order_id}
        if details:
            merged.update(details)
        super().__init__(message=message, details=merged)


class PaperSLTPPlacementError(PaperOrderError):
    """SL/TP conditional order placement failed on exchange."""

    def __init__(
        self,
        exchange_id: str,
        strategy: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = {"exchange_id": exchange_id, "strategy": strategy}
        if details:
            merged.update(details)
        final_message = message or f"SL/TP placement failed on {exchange_id} ({strategy})"
        super().__init__(message=final_message, details=merged)


class PaperInsufficientMarginError(PaperOrderError):
    """Margin balance insufficient for paper futures order."""

    def __init__(
        self,
        message: str = "Insufficient margin balance for paper futures order",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)


_CCXT_ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.CCXT_INSUFFICIENT_FUNDS: HTTP_CLIENT_ERROR,
    ErrorCode.CCXT_INVALID_ORDER: HTTP_CLIENT_ERROR,
    ErrorCode.CCXT_BAD_SYMBOL: HTTP_CLIENT_ERROR,
    ErrorCode.CCXT_AUTH_FAILED: HTTP_CLIENT_ERROR,
    ErrorCode.CCXT_RATE_LIMITED: HTTP_RATE_LIMIT,
    ErrorCode.CCXT_EXCHANGE_UNAVAILABLE: HTTP_SERVICE_UNAVAILABLE,
    ErrorCode.CCXT_NETWORK_ERROR: HTTP_SERVICE_UNAVAILABLE,
    ErrorCode.CCXT_UNKNOWN: HTTP_SERVICE_UNAVAILABLE,
}


class VenueOrderError(PulsAIException):
    """Exchange adapter call failed with a mapped ``ccxt.BaseError`` (B6.8).

    Carries a stable :class:`ErrorCode` and a safe, i18n-ready message — the
    raw CCXT message is never attached to the public payload. Callers log
    the raw exception server-side before raising this.
    """

    def __init__(
        self,
        *,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=_CCXT_ERROR_STATUS.get(code, HTTP_SERVICE_UNAVAILABLE),
            details=details or {},
        )


class PaperTradingPreflightError(PulsAIException):
    """
    Paper order blocked before CCXT ``create_order`` (balance / margin / reference price).

    Maps to HTTP 400 with a stable ``ErrorCode`` for clients (automation executor, manual API).
    """

    def __init__(
        self,
        *,
        message: str,
        code: ErrorCode,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=HTTP_CLIENT_ERROR,
            details=details or {},
        )


class PaperCompoundDirectionError(TradingDomainError):
    """User attempted to average in wrong direction (e.g., average up on long)."""

    def __init__(
        self,
        side: str,
        current_price: str,
        avg_entry: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = {
            "side": side,
            "current_price": current_price,
            "avg_entry": avg_entry,
        }
        if details:
            merged.update(details)
        direction = "down" if side == ORDER_SIDE_BUY else "up"
        final_message = message or (
            f"Compound guard: {side} orders must average {direction}. Current price {current_price} vs avg entry {avg_entry}."
        )
        super().__init__(message=final_message, details=merged)


class PaperCompoundCapExceededError(TradingDomainError):
    """Position has reached the configured max compound fill count for this order."""

    def __init__(
        self,
        *,
        fill_count: int,
        max_compound_trades: int,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = {
            "fill_count": fill_count,
            "max_compound_trades": max_compound_trades,
        }
        if details:
            merged.update(details)
        final_message = message or (f"Compound cap reached: {fill_count} fills (limit {max_compound_trades}).")
        super().__init__(message=final_message, details=merged)


class PaperCompoundStepError(TradingDomainError):
    """Compound fill did not move enough vs last fill (min_compound_step_pct ladder)."""

    def __init__(
        self,
        *,
        side: str,
        last_fill_price: str,
        fill_price: str,
        min_step_pct: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = {
            "side": side,
            "last_fill_price": last_fill_price,
            "fill_price": fill_price,
            "min_step_pct": min_step_pct,
        }
        if details:
            merged.update(details)
        final_message = message or (
            f"Compound min_step: {side} requires ≥{min_step_pct}% favorable move from last fill ({last_fill_price} → {fill_price})."
        )
        super().__init__(message=final_message, details=merged)
