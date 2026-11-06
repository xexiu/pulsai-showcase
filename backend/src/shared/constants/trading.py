"""
Trading defaults shared across backend entry points.

WHY centralize these literals?
- Training schemas, pipelines, and settings all need the same defaults
- Repeating BTC/USDT, 1h, and binance in multiple layers creates drift
- Shared constants keep defaults explicit without importing runtime settings

Epic B (RefactorHuge) folded the surviving subset of ``paper_trading.py`` in
here — order side/type, trading-mode literals, SL/TP brackets, shared error
detail strings, and CCXT clientOrderId limits. The paper-specific order-status
/ event-type / mirror / fill-resolution / retention constants were deleted
along with the BE order-state machinery; only the constants still referenced
by the demo + auto + FE-direct surfaces survive here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, Literal

from src.domain.enums import Exchange
from src.shared.constants.http_idempotency import HTTP_IDEMPOTENCY_KEY_MAX_LEN
from src.shared.constants.timeframes import DEFAULT_TIMEFRAME

DEFAULT_SYMBOL = "BTC/USDT"
DEFAULT_SYMBOLS: list[str] = [DEFAULT_SYMBOL]

# Every symbol the product supports, in product order (the first is the default). SoT for the
# ``supported_symbols`` settings default, for the shared-package registry (parity-tested by
# tests/unit/shared/constants/test_symbol_frontend_parity.py) and for the news coin-name contract.
# Mirrors DEFAULT_SUPPORTED_TIMEFRAME_VALUES. Not DEFAULT_SYMBOLS above, which is the single-symbol
# default for features that run on one market only.
DEFAULT_SUPPORTED_SYMBOL_VALUES: Final[tuple[str, ...]] = (DEFAULT_SYMBOL, "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT")
DEFAULT_EXCHANGE = Exchange.BINANCE.value
SUPPORTED_EXCHANGE_VALUES: list[str] = [exchange.value for exchange in Exchange]

VOLUME_SPIKE_THRESHOLD = 2.0
"""
SoT for volume spike detection threshold.

Volume must be this multiple of its SMA to be considered a "spike."
Used by BOTH:
- VolumeBreakoutDetector (classic signal pipeline, row-by-row)
- _calculate_volume_spike() (feature pipeline, vectorized numpy)

WHY 2.0: Volume at 2x the 20-bar SMA indicates strong market participation.
Below 2x, most "spikes" are just normal variance.
"""


def get_supported_exchanges(configured_exchanges: str | None) -> list[str]:
    """
    Resolve configured exchanges as a validated subset of the backend exchange registry.

    Blank configuration means "all backend-supported trading exchanges".
    Unknown values fail fast so the frontend cannot advertise unsupported runtime paths.
    """
    if not configured_exchanges or not configured_exchanges.strip():
        return SUPPORTED_EXCHANGE_VALUES.copy()

    requested = [exchange.strip() for exchange in configured_exchanges.split(",") if exchange.strip()]
    unknown = [exchange for exchange in requested if exchange not in SUPPORTED_EXCHANGE_VALUES]
    if unknown:
        raise ValueError(f"Unsupported exchanges in config: {unknown}. Supported: {SUPPORTED_EXCHANGE_VALUES}")

    deduped: list[str] = []
    seen: set[str] = set()
    for exchange in requested:
        if exchange in seen:
            continue
        seen.add(exchange)
        deduped.append(exchange)
    return deduped


NEAR_ZERO_EPSILON: Final[Decimal] = Decimal("-1e-12")

# ── Order side / type / trading mode / margin (SoT for API + domain) ──

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
# Epic B: paper BE trading deleted; manual paper/live moved to FE-direct.
# ``live`` still survives on the wire (``/trading/modes`` advertises it as a
# pointer to the FE-direct surface) but the BE only persists ``demo`` rows.
TradingMode = Literal["demo", "live"]

ORDER_SIDE_BUY: Final[Literal["buy"]] = "buy"
ORDER_SIDE_SELL: Final[Literal["sell"]] = "sell"

ORDER_TYPE_MARKET: Final[Literal["market"]] = "market"
ORDER_TYPE_LIMIT: Final[Literal["limit"]] = "limit"

TRADING_MODE_DEMO: Final[Literal["demo"]] = "demo"
TRADING_MODE_LIVE: Final[Literal["live"]] = "live"
# Epic B kept this literal so a few dead-but-still-imported checks compile.
# No BE write path persists ``paper`` rows; eligible for B8 removal once the
# residual call sites in trading_schemas + trading_live_execution_mode are
# deleted (they describe a now-defunct paper partition).
TRADING_MODE_PAPER: Final[Literal["paper"]] = "paper"

# JSON field on each GET /trading/modes item — whether the venue supports USDT-M swap.
TRADING_MODES_JSON_KEY_FUTURES_SUPPORTED: Final[str] = "futures_paper_supported"

DEFAULT_MARGIN_ASSET: Final[str] = "USDT"

# Outbound ``params["clientOrderId"]`` wire cap — Binance futures clientOrderId max is 36 (strictest integrated venue).
CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN: Final[int] = 36
CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX: Final[str] = "pul-f"
CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_FIRST: Final[int] = 12
CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_SECOND: Final[int] = 10

# Re-export from the HTTP SoT (parity across demo/HTTP receipts).
TRADING_IDEMPOTENCY_KEY_MAX_LEN: Final[int] = HTTP_IDEMPOTENCY_KEY_MAX_LEN

# ── Audit placed_by SoT ──
PlacedBy = Literal["manual", "auto"]

PLACED_BY_MANUAL: Final[PlacedBy] = "manual"
PLACED_BY_AUTO: Final[PlacedBy] = "auto"

UNKNOWN_TRADING_MODE_PREFIX: Final[str] = "Unknown mode: "

# ── Feature gates / API error detail strings ──
FUTURES_NOT_ENABLED_DETAIL: Final[str] = "Futures paper trading is not enabled."
LIVE_NOT_ENABLED_DETAIL: Final[str] = "Live trading is not enabled."
LIVE_EXECUTION_NOT_IMPLEMENTED_DETAIL: Final[str] = "Live trading execution is not implemented yet."
LIVE_REQUIRES_MAINNET_CONNECTION_DETAIL: Final[str] = "Live trading requires mainnet API credentials on this connection (mainnet_execution_enabled)."

# ── Standard error detail strings (API + domain) ──
CONNECTION_NOT_FOUND_DETAIL: Final[str] = "Connection not found"
CONNECTION_NOT_ACTIVE_DETAIL: Final[str] = "Connection is not active"
CONNECTION_DISCONNECTED_DETAIL: Final[str] = "Connection is disconnected"
ORDER_NOT_FOUND_DETAIL: Final[str] = "Order not found"
ORDER_NOT_CANCELLABLE_DETAIL: Final[str] = "Order not found or not cancellable"
ORDER_MISSING_AFTER_CANCEL_DETAIL: Final[str] = "Order missing after cancel"
TRADING_MODE_MISMATCH_DETAIL: Final[str] = "Trading mode does not match order"
IDEMPOTENCY_REFERENCES_MISSING_ORDER_DETAIL: Final[str] = "Idempotency record references missing order"
IDEMPOTENCY_KEY_TOO_LONG_DETAIL: Final[str] = "Idempotency-Key is too long"
INSUFFICIENT_USD_DETAIL: Final[str] = "Insufficient USD balance"
INSUFFICIENT_BTC_DETAIL: Final[str] = "Insufficient BTC balance"
SIDE_INVALID_DETAIL: Final[str] = "side must be buy or sell"
MARKET_VENUE_LIMITS_REFERENCE_REQUIRED_DETAIL: Final[str] = (
    "A reference price is required to validate this market order against venue minimums (supply reference_price or ensure ticker data is available)."
)
COMPOUND_V2_SCHEDULE_SWAP_ONLY_DETAIL: Final[str] = "compound_leg_schedule_v2 is only valid for futures (swap) orders."
DEMO_SELL_BRACKET_DETAIL: Final[str] = "Stop loss and take profit are not supported for demo sell orders."

# ── SL/TP bracket statuses ──
BracketStatus = Literal["pending", "triggered", "cancelled"]

BRACKET_STATUS_PENDING: Final[BracketStatus] = "pending"
BRACKET_STATUS_TRIGGERED: Final[BracketStatus] = "triggered"
BRACKET_STATUS_CANCELLED: Final[BracketStatus] = "cancelled"

# ── SL/TP execution strategy ──
SLTPStrategy = Literal["exchange_native", "exchange_spot_plan"]

SLTP_STRATEGY_EXCHANGE_NATIVE: Final[SLTPStrategy] = "exchange_native"
SLTP_STRATEGY_EXCHANGE_SPOT_PLAN: Final[SLTPStrategy] = "exchange_spot_plan"

# ── SL/TP pricing mode ──
SLTPMode = Literal["absolute", "percentage"]

SLTP_MODE_ABSOLUTE: Final[SLTPMode] = "absolute"
SLTP_MODE_PERCENTAGE: Final[SLTPMode] = "percentage"


__all__ = [
    "BRACKET_STATUS_CANCELLED",
    "BRACKET_STATUS_PENDING",
    "BRACKET_STATUS_TRIGGERED",
    "CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_FIRST",
    "CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_SECOND",
    "CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX",
    "CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN",
    "COMPOUND_V2_SCHEDULE_SWAP_ONLY_DETAIL",
    "CONNECTION_DISCONNECTED_DETAIL",
    "CONNECTION_NOT_ACTIVE_DETAIL",
    "CONNECTION_NOT_FOUND_DETAIL",
    "DEFAULT_EXCHANGE",
    "DEFAULT_MARGIN_ASSET",
    "DEFAULT_SUPPORTED_SYMBOL_VALUES",
    "DEFAULT_SYMBOL",
    "DEFAULT_SYMBOLS",
    "DEFAULT_TIMEFRAME",
    "DEMO_SELL_BRACKET_DETAIL",
    "FUTURES_NOT_ENABLED_DETAIL",
    "IDEMPOTENCY_KEY_TOO_LONG_DETAIL",
    "IDEMPOTENCY_REFERENCES_MISSING_ORDER_DETAIL",
    "INSUFFICIENT_BTC_DETAIL",
    "INSUFFICIENT_USD_DETAIL",
    "LIVE_EXECUTION_NOT_IMPLEMENTED_DETAIL",
    "LIVE_NOT_ENABLED_DETAIL",
    "LIVE_REQUIRES_MAINNET_CONNECTION_DETAIL",
    "MARKET_VENUE_LIMITS_REFERENCE_REQUIRED_DETAIL",
    "NEAR_ZERO_EPSILON",
    "ORDER_MISSING_AFTER_CANCEL_DETAIL",
    "ORDER_NOT_CANCELLABLE_DETAIL",
    "ORDER_NOT_FOUND_DETAIL",
    "ORDER_SIDE_BUY",
    "ORDER_SIDE_SELL",
    "ORDER_TYPE_LIMIT",
    "ORDER_TYPE_MARKET",
    "PLACED_BY_AUTO",
    "PLACED_BY_MANUAL",
    "SIDE_INVALID_DETAIL",
    "SLTP_MODE_ABSOLUTE",
    "SLTP_MODE_PERCENTAGE",
    "SLTP_STRATEGY_EXCHANGE_NATIVE",
    "SLTP_STRATEGY_EXCHANGE_SPOT_PLAN",
    "SUPPORTED_EXCHANGE_VALUES",
    "TRADING_IDEMPOTENCY_KEY_MAX_LEN",
    "TRADING_MODES_JSON_KEY_FUTURES_SUPPORTED",
    "TRADING_MODE_DEMO",
    "TRADING_MODE_LIVE",
    "TRADING_MODE_MISMATCH_DETAIL",
    "TRADING_MODE_PAPER",
    "UNKNOWN_TRADING_MODE_PREFIX",
    "VOLUME_SPIKE_THRESHOLD",
    "BracketStatus",
    "OrderSide",
    "OrderType",
    "PlacedBy",
    "SLTPMode",
    "SLTPStrategy",
    "TradingMode",
    "get_supported_exchanges",
]
