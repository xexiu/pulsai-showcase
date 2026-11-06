"""
Symbol format conversion utilities.

Symbol formats in PulsAI:
- Standard: "BTC/USDT" (exchange format, used in CCXT and most places)
- Safe key: "btc_usdt" (cache keys, filenames, model names - no special chars)
- URL: "btc-usdt" (URL-safe for API route parameters)
- Short: "BTC" (display purposes, removes USDT suffix)

WHY centralize this?
- 45+ occurrences of symbol.replace() scattered across 24 files
- Inconsistent handling (some uppercase, some lowercase)
- DRY violation creating maintenance burden

@see docs/04-structural/CODING_STANDARDS.md - Section 2.0 DON'T REINVENT THE WHEEL
"""


def symbol_to_safe_key(symbol: str) -> str:
    """
    Convert standard symbol to safe key format.

    BTC/USDT -> btc_usdt

    Used for:
    - Cache keys (Redis)
    - Filenames (model storage)
    - Optuna study names
    - Database identifiers

    Args:
        symbol: Standard symbol format (e.g., "BTC/USDT")

    Returns:
        Safe key format (e.g., "btc_usdt")

    Examples:
        >>> symbol_to_safe_key("BTC/USDT")
        'btc_usdt'
        >>> symbol_to_safe_key("ETH/BTC")
        'eth_btc'
    """
    return symbol.strip().lower().replace("/", "_")


def symbol_to_exchange_namespaced_segment(symbol: str) -> str:
    """
    Phase 2 exchange-scoped Redis key segment (uppercase ``BTC_USDT``).

    Differs from ``symbol_to_safe_key`` (lowercase ``btc_usdt``): namespaced
    OHLCV keys intentionally use uppercase so ``redis-cli KEYS ohlcv:*`` is
    human-readable and cannot be confused with legacy ``ohlcv:btc_usdt:*``.

    SoT: ``CacheKeys.ohlcv_exchange_tail`` / ``ohlcv_exchange_fresh_heartbeat``,
    ``OHLCVStreamSupervisor``, ``OHLCVService`` Phase 2 reader.

    Args:
        symbol: Unified CCXT symbol (e.g. ``BTC/USDT``).

    Returns:
        Segment like ``BTC_USDT``.
    """
    return symbol.strip().replace("/", "_").upper()


def symbol_from_safe_key(safe_key: str) -> str:
    """
    Convert safe key back to standard symbol format.

    btc_usdt -> BTC/USDT

    Used for:
    - Converting cache keys back to exchange format
    - API responses that need standard format

    Args:
        safe_key: Safe key format (e.g., "btc_usdt")

    Returns:
        Standard symbol format (e.g., "BTC/USDT")

    Examples:
        >>> symbol_from_safe_key("btc_usdt")
        'BTC/USDT'
    """
    return safe_key.strip().upper().replace("_", "/")


def symbol_from_url(url_symbol: str) -> str:
    """
    Convert URL-safe symbol to standard format.

    btc-usdt -> BTC/USDT

    Used for:
    - API route parameters (e.g., /models/btc-usdt/1h)
    - FastAPI path parameters

    Args:
        url_symbol: URL-safe format (e.g., "btc-usdt")

    Returns:
        Standard symbol format (e.g., "BTC/USDT")

    Examples:
        >>> symbol_from_url("btc-usdt")
        'BTC/USDT'
    """
    return url_symbol.strip().upper().replace("-", "/")


def symbol_short(symbol: str) -> str:
    """
    Get short symbol name (base currency only).

    BTC/USDT -> BTC
    BTCUSDT -> BTC

    Used for:
    - Display purposes (Telegram messages, notifications)
    - Compact UI elements

    Args:
        symbol: Symbol in any format

    Returns:
        Short base currency (e.g., "BTC")

    Examples:
        >>> symbol_short("BTC/USDT")
        'BTC'
        >>> symbol_short("ETHUSDT")
        'ETH'
    """
    # Handle both "BTC/USDT" and "BTCUSDT" formats
    return symbol.replace("/USDT", "").replace("USDT", "")
