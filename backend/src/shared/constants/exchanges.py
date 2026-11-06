"""
Exchange identifiers and testnet support — SoT for user exchange connections & paper trading.

@see docs/03-functional — Signal Dashboard + Paper Trading plan (AD-6, Phase 4A).
"""

from decimal import Decimal
from typing import Final, Literal

from src.shared.constants.paper_trading import ORDER_TYPE_LIMIT, ORDER_TYPE_MARKET, OrderType
from src.shared.constants.trading_execution_defaults import DEFAULT_DEMO_TAKER_FEE_RATE

# Phase 2.7.1 deprecation shim: ``OrderType`` / ``ORDER_TYPE_MARKET`` /
# ``ORDER_TYPE_LIMIT`` live canonically in :mod:`src.shared.constants.paper_trading`.
# Listed in ``__all__`` so existing ``from src.shared.constants.exchanges import OrderType``
# call sites stay valid until removal in Phase 2.8 (and so static analysis
# doesn't flag the imports as unused).
__all__ = [
    "CONNECTION_DISCONNECTED_RECONNECT_DETAIL",
    "CONNECTION_STATUS_ACTIVE",
    "CONNECTION_STATUS_DISCONNECTED",
    "CONNECTION_STATUS_INVALID",
    "DEFAULT_DEMO_BALANCE_USD",
    "DEFAULT_DEMO_TRADING_SYMBOL",
    "DEFAULT_FEE_RATE",
    "DEFAULT_FUTURES_MARGIN_MODE",
    "DEFAULT_SWAP_PROBE_SYMBOLS",
    "EXCHANGES_WITH_TESTNET",
    "EXCHANGE_ID_BINANCE",
    "EXCHANGE_ID_BITGET",
    "EXCHANGE_KEY_TESTNET_AUTH_FAILED_PREFIX",
    "EXCHANGE_NOT_SUPPORTED_DETAIL_PREFIX",
    "EXCHANGE_VERIFICATION_FAILED_PREFIX",
    "EXCHANGE_VERIFY_FAILED_PREFIX",
    "FUTURES_PAPER_SUPPORTED_EXCHANGES",
    "MARKET_TYPE_SPOT",
    "MARKET_TYPE_SWAP",
    "MAX_LEVERAGE",
    "MIN_LEVERAGE",
    "ORDER_TYPE_LIMIT",
    "ORDER_TYPE_MARKET",
    "SUPPORTED_EXCHANGES",
    "ConnectionStatus",
    "MarketType",
    "OrderType",
    "exchange_not_supported_detail",
    "exchange_supports_futures_paper",
    "exchange_supports_testnet",
]

# Canonical CCXT id for Binance (CCXT lowercase). Use for string comparisons — no scattered literals.
EXCHANGE_ID_BINANCE: Final[str] = "binance"

# Canonical CCXT id for Bitget (CCXT lowercase). Use for string comparisons — no scattered literals.
EXCHANGE_ID_BITGET: Final[str] = "bitget"

# Exchanges where CCXT swap / USDT-M paper is supported in product (align with BE paper order paths).
#
# Order intentionally matches the canonical SoT in
# ``packages/shared/src/constants/exchanges.ts`` (EXCHANGE_IDS) so the parity
# test in ``tests/unit/shared/constants/test_exchange_ids_parity.py`` passes.
# When adding a venue: update the TS SoT first, then mirror the change here.
# See ``docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md`` for the rationale.
FUTURES_PAPER_SUPPORTED_EXCHANGES: Final[frozenset[str]] = frozenset(
    {
        EXCHANGE_ID_BINANCE,
        "bitget",
        "bybit",
        "okx",
    }
)

MarketType = Literal["spot", "swap"]

MARKET_TYPE_SPOT: Final[MarketType] = "spot"
MARKET_TYPE_SWAP: Final[MarketType] = "swap"

# ── Exchange connection lifecycle status (SoT for user_exchange_connections.status column) ──

ConnectionStatus = Literal["active", "disconnected", "invalid"]

CONNECTION_STATUS_ACTIVE: Final[ConnectionStatus] = "active"
CONNECTION_STATUS_DISCONNECTED: Final[ConnectionStatus] = "disconnected"
CONNECTION_STATUS_INVALID: Final[ConnectionStatus] = "invalid"

# Stable service→HTTP boundary messages for exchange connect/verify (i18n SoT).
EXCHANGE_NOT_SUPPORTED_DETAIL_PREFIX: Final[str] = "Exchange not supported:"
CONNECTION_DISCONNECTED_RECONNECT_DETAIL: Final[str] = "Connection is disconnected; connect again with new keys"
EXCHANGE_KEY_TESTNET_AUTH_FAILED_PREFIX: Final[str] = "This key does not work on"
EXCHANGE_VERIFICATION_FAILED_PREFIX: Final[str] = "Exchange verification failed:"
EXCHANGE_VERIFY_FAILED_PREFIX: Final[str] = "Verification failed:"


def exchange_not_supported_detail(exchange_id: str) -> str:
    """Build the canonical unsupported-exchange rejection message."""
    return f"{EXCHANGE_NOT_SUPPORTED_DETAIL_PREFIX} {exchange_id}"


# Canonical CCXT ids (lowercase) for supported user connections.
#
# **Order must match** ``packages/shared/src/constants/exchanges.ts``
# (EXCHANGE_IDS). The parity test
# ``tests/unit/shared/constants/test_exchange_ids_parity.py`` asserts exact
# tuple equality on both sides so drift between FE+BE is impossible at CI.
SUPPORTED_EXCHANGES: Final[tuple[str, ...]] = (
    EXCHANGE_ID_BINANCE,
    "bitget",
    "bybit",
    "okx",
    "coinbase",
    "kraken",
)

# Whether the exchange exposes a CCXT sandbox/testnet suitable for paper keys.
# Mirrors ``EXCHANGE_CAPABILITIES[*].testnet`` in the TS SoT.
EXCHANGES_WITH_TESTNET: Final[dict[str, bool]] = {
    EXCHANGE_ID_BINANCE: True,
    "bitget": True,
    "bybit": True,
    "okx": True,
    "coinbase": False,
    "kraken": False,
}

# Fallback fee for demo mode only (PulsAI-managed portfolio); same SoT as `fees.DEFAULT_FEE_RATE`.
DEFAULT_FEE_RATE: Final[Decimal] = DEFAULT_DEMO_TAKER_FEE_RATE

# Default demo portfolio (USD notional).
DEFAULT_DEMO_BALANCE_USD: Final[Decimal] = Decimal(10000)
_TWO: Final[Decimal] = Decimal(2)


# Default spot pair for demo CCXT-less orders and trading API (must match FE `PAPER_TRADING_DEFAULT_ORDER_SYMBOL`).
DEFAULT_DEMO_TRADING_SYMBOL: Final[str] = "BTC/USDT"

# Default swap symbols used by venue probe queries when a per-symbol fetch
# is required (e.g. Bitget orders-history needs a symbol filter to return
# rows). Keep narrow — broaden when a new multi-symbol probe is added.
# RefactorHuge §4.3.
DEFAULT_SWAP_PROBE_SYMBOLS: Final[tuple[str, ...]] = ("BTC/USDT:USDT",)


# ── Futures paper trading defaults ──
DEFAULT_FUTURES_MARGIN_MODE: Final[str] = "isolated"
MIN_LEVERAGE: Final[int] = 3
MAX_LEVERAGE: Final[int] = 100


def exchange_supports_testnet(exchange_id: str) -> bool:
    """Return True if exchange typically has CCXT sandbox/testnet."""
    return EXCHANGES_WITH_TESTNET.get(exchange_id.lower(), False)


def exchange_supports_futures_paper(exchange_id: str) -> bool:
    """Return True if this exchange id supports perpetual (swap) paper trading in PulsAI."""
    return exchange_id.lower() in FUTURES_PAPER_SUPPORTED_EXCHANGES
