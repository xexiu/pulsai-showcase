"""Curated news names for supported coins (2026-09-11).

Tickers are matched automatically from the supported-symbol SoT (``DEFAULT_SUPPORTED_SYMBOL_VALUES``
and ``settings.supported_symbols_list``), so a coin added only through configuration is still caught
by its ticker. Headlines also name coins in words ("Bitcoin", "Ether", "Ripple"), which a ticker
cannot catch; those names live here, keyed by base ticker.
``tests/unit/domain/services/test_crypto_news_relevance.py`` fails when a default-supported coin has
no entry, so adding a coin cannot silently leave the news pipeline blind to its name.

Names are lowercase and matched case-insensitively on word boundaries.

REUSE-AUDIT: considered src/domain/services/news_macro_router.py::MACRO_KEYWORDS (macro/geopolitical
routing terms, a different concept) and src/domain/services/edge_book_settings.py::EDGE_BOOK_UNIVERSE
(tickers only, no names); neither maps a coin to the words headlines use for it.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

CRYPTO_ASSET_NEWS_NAMES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "BTC": ("bitcoin",),
        "ETH": ("ethereum", "ether"),
        "SOL": ("solana",),
        "XRP": ("ripple",),
        "BNB": ("binance coin", "bnb chain"),
    }
)

# Crypto words that make a headline crypto-relevant without naming a coin.
CRYPTO_NEWS_GENERIC_TERMS: Final[tuple[str, ...]] = (
    "crypto",
    "cryptocurrency",
    "cryptocurrencies",
    "stablecoin",
    "stablecoins",
    "altcoin",
    "altcoins",
    "blockchain",
    "defi",
    "memecoin",
    "memecoins",
)

# The ai-sources.yaml category that marks a feed as a crypto newsroom: every headline from such a feed
# is crypto news even when it names no coin. Read from config, so a newsroom is added in YAML, not code.
CRYPTO_NEWS_SOURCE_CATEGORY: Final[str] = "crypto"
