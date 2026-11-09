"""Typed errors for derivatives data vendors (Coinglass)."""

from __future__ import annotations


class DerivativesVendorError(Exception):
    """Base class for third-party derivatives API failures."""


class CoinglassError(DerivativesVendorError):
    """Coinglass client failure."""


class CoinglassNotConfiguredError(CoinglassError):
    """API key missing (caller should fail-closed or skip live call)."""


class CoinglassHTTPError(CoinglassError):
    """Non-success HTTP from Coinglass."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class CoinglassAuthError(CoinglassHTTPError):
    """401/403 from Coinglass — key missing or plan insufficient."""


class CoinglassRateLimitError(CoinglassHTTPError):
    """429 from Coinglass — rate limit exceeded."""


class CoinglassPayloadError(CoinglassError):
    """Unusable JSON or unexpected envelope shape."""


class CoinglassPlanError(CoinglassError):
    """The requested endpoint or history range requires a paid plan.

    Attributes:
        required_plan: human-readable plan name (e.g. ``"Starter"``).
        endpoint: the path that was denied.
    """

    def __init__(
        self,
        message: str,
        *,
        required_plan: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.required_plan = required_plan
        self.endpoint = endpoint
