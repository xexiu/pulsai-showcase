"""``ErrorCode`` -- the stable API error-code enum (re-exported by ``src.shared.exceptions``)."""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Standard error codes for PulsAI API."""

    # --- Authentication (401) ---
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"

    # --- Forbidden (403) ---
    FORBIDDEN = "FORBIDDEN"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    LEGAL_CONSENT_REQUIRED = "LEGAL_CONSENT_REQUIRED"
    # P3-MED-5: typed rejections for the paper-trade router so locale-aware
    # clients do not fall back to raw English ValueError messages.
    FUTURES_ADMIN_ONLY = "FUTURES_ADMIN_ONLY"
    LIVE_TRADING_NOT_ENABLED = "LIVE_TRADING_NOT_ENABLED"

    # --- Validation (400) ---
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    # P3-MED-5: typed 400s for user-facing paper/live-order rejections so FE
    # locales map codes → translated strings (no English passthrough).
    CONNECTION_NOT_ACTIVE = "CONNECTION_NOT_ACTIVE"
    LIVE_TRADING_REQUIRES_MAINNET = "LIVE_TRADING_REQUIRES_MAINNET"
    FUTURES_NOT_ENABLED = "FUTURES_NOT_ENABLED"
    # Paper CCXT preflight (400) — stable client codes (slice-05 / ADR-009 capital gates)
    PAPER_INSUFFICIENT_FUTURES_MARGIN = "PAPER_INSUFFICIENT_FUTURES_MARGIN"
    PAPER_INSUFFICIENT_SPOT_QUOTE = "PAPER_INSUFFICIENT_SPOT_QUOTE"
    PAPER_INSUFFICIENT_SPOT_BASE = "PAPER_INSUFFICIENT_SPOT_BASE"
    PAPER_TRADING_REFERENCE_PRICE_REQUIRED = "PAPER_TRADING_REFERENCE_PRICE_REQUIRED"
    PAPER_EXCHANGE_BALANCE_UNAVAILABLE = "PAPER_EXCHANGE_BALANCE_UNAVAILABLE"
    # Spot order debits spot wallet only; merged balance can include futures/swap (e.g. Bitget).
    PAPER_SPOT_QUOTE_IN_FUTURES_WALLET = "PAPER_SPOT_QUOTE_IN_FUTURES_WALLET"
    # Phase 2 preflight (B6) — market-structure gates before adapter dispatch.
    PAPER_PREFLIGHT_AMOUNT_BELOW_MIN = "PAPER_PREFLIGHT_AMOUNT_BELOW_MIN"
    PAPER_PREFLIGHT_MIN_NOTIONAL = "PAPER_PREFLIGHT_MIN_NOTIONAL"
    PAPER_PREFLIGHT_PRICE_DEVIATION = "PAPER_PREFLIGHT_PRICE_DEVIATION"
    PAPER_PREFLIGHT_OPEN_ORDER_CAP = "PAPER_PREFLIGHT_OPEN_ORDER_CAP"
    PAPER_PREFLIGHT_LEVERAGE_EXCEEDS_VENUE_MAX = "PAPER_PREFLIGHT_LEVERAGE_EXCEEDS_VENUE_MAX"
    PAPER_PREFLIGHT_AMOUNT_NOT_ON_STEP = "PAPER_PREFLIGHT_AMOUNT_NOT_ON_STEP"
    PAPER_PREFLIGHT_PRICE_NOT_ON_TICK = "PAPER_PREFLIGHT_PRICE_NOT_ON_TICK"
    # Q7 — SL/TP sanity preflight (Phase 2 multi-exchange auto-trade).
    PAPER_PREFLIGHT_SLTP_NON_POSITIVE = "PAPER_PREFLIGHT_SLTP_NON_POSITIVE"
    PAPER_PREFLIGHT_SLTP_WRONG_SIDE = "PAPER_PREFLIGHT_SLTP_WRONG_SIDE"
    # Spot plan-bracket policy (registry); detail strings match ``spot_bracket_errors``.
    SPOT_BRACKET_UNSUPPORTED_VENUE = "SPOT_BRACKET_UNSUPPORTED_VENUE"
    SPOT_BRACKET_NOT_IMPLEMENTED = "SPOT_BRACKET_NOT_IMPLEMENTED"
    SPOT_BRACKET_SPOT_SELL_BRACKET = "SPOT_BRACKET_SPOT_SELL_BRACKET"
    # CCXT/network failure while loading venue market limits — fail-closed, not a silent skip.
    PAPER_PREFLIGHT_LIMITS_FETCH_FAILED = "PAPER_PREFLIGHT_LIMITS_FETCH_FAILED"
    # CCXT venue errors (B6.8) — stable codes; raw venue text never leaves the server.
    CCXT_INSUFFICIENT_FUNDS = "CCXT_INSUFFICIENT_FUNDS"
    CCXT_INVALID_ORDER = "CCXT_INVALID_ORDER"
    CCXT_BAD_SYMBOL = "CCXT_BAD_SYMBOL"
    CCXT_RATE_LIMITED = "CCXT_RATE_LIMITED"
    CCXT_AUTH_FAILED = "CCXT_AUTH_FAILED"
    CCXT_EXCHANGE_UNAVAILABLE = "CCXT_EXCHANGE_UNAVAILABLE"
    CCXT_NETWORK_ERROR = "CCXT_NETWORK_ERROR"
    CCXT_UNKNOWN = "CCXT_UNKNOWN"

    # --- Unprocessable entity (422) — business rule / invariant ---
    EXECUTION_LEG_INCOMPATIBLE_WITH_SNAPSHOT = "EXECUTION_LEG_INCOMPATIBLE_WITH_SNAPSHOT"
    FULL_AUTO_TRADING_CONSENT_REQUIRED = "FULL_AUTO_TRADING_CONSENT_REQUIRED"
    # Compound v1 anchor-leg invariants. The two specific codes below replace
    # the ambiguous legacy ``COMPOUND_V1_LEG_MISMATCH`` so FE/i18n (and
    # server-side retry helpers) can disambiguate leverage vs. notional
    # failures without parsing error messages. The legacy code is retained
    # on the enum for back-compat with external consumers and historical
    # audit log entries; no new raise site uses it.
    COMPOUND_V1_LEVERAGE_MISMATCH = "COMPOUND_V1_LEVERAGE_MISMATCH"
    COMPOUND_V1_NOTIONAL_MISMATCH = "COMPOUND_V1_NOTIONAL_MISMATCH"
    # Compound v2: follow-on DCA limits must not cross the anchor stop-loss.
    COMPOUND_V2_LEG_CROSS_STOP_LOSS = "COMPOUND_V2_LEG_CROSS_STOP_LOSS"
    COMPOUND_V1_LEG_MISMATCH = "COMPOUND_V1_LEG_MISMATCH"  # deprecated alias

    # --- Not Found (404) ---
    NOT_FOUND = "NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    SIGNAL_NOT_FOUND = "SIGNAL_NOT_FOUND"
    # P3-MED-5: user asked the service to act on a connection row that either
    # doesn't belong to them (IDOR remediation) or no longer exists.
    CONNECTION_NOT_FOUND = "CONNECTION_NOT_FOUND"

    # --- Conflict (409) ---
    CONFLICT = "CONFLICT"
    IDEMPOTENCY_KEY_REUSE = "IDEMPOTENCY_KEY_REUSE"
    MODEL_STORAGE_CAP_EXCEEDED = "MODEL_STORAGE_CAP_EXCEEDED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    EMAIL_EXISTS = "EMAIL_EXISTS"
    NEWSLETTER_EMAIL_EXISTS = "NEWSLETTER_EMAIL_EXISTS"

    # --- Rate Limit (429) ---
    RATE_LIMITED = "RATE_LIMITED"

    # --- Service unavailable / maintenance (503) ---
    SERVICE_PAUSED = "SERVICE_PAUSED"
    #: The token-revocation backend could not be reached. NOT `INVALID_TOKEN`: the session may be
    #: perfectly valid and we simply cannot check it, and a client that cannot tell those apart
    #: signs the user out for an outage that lasted seconds.
    AUTH_BACKEND_UNAVAILABLE = "AUTH_BACKEND_UNAVAILABLE"

    # --- Server Error (500) ---
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
