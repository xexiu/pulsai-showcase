"""Crypto relevance for news headlines, derived from the supported-symbol SoT (2026-09-11).

Owner, after a CPI whipsaw no alert caught: "When BTC news, or any crypto news (ltc, eth, bnb, etc)
we should catch it and maybe add a bit more weights ... If someone/dev adds a new coin/symbol, the
news MUST include it also and catch it."

Measured the same day: the headline pipeline scored ~87 headlines per cycle, ~24 of them from
crypto newsrooms, and treated every one identically — no notion of which coin a headline is about.
These tests pin both halves of the ask: every supported coin is caught by ticker AND by name, and a
coin added only through configuration is still caught by its ticker.

REUSE-AUDIT: considered src/domain/services/news_macro_router.py (the macro keyword router — its
word-bounded pattern style is reused, the router is not extended: macro routing and coin relevance
answer different questions and feed different weights) and src/shared/utils/symbols.py::symbol_short
(reused for the base ticker).
"""

from __future__ import annotations

import pytest

from src.domain.services.crypto_news_relevance import crypto_news_coverage, crypto_symbols_mentioned
from src.shared.constants.crypto_news_assets import CRYPTO_ASSET_NEWS_NAMES
from src.shared.constants.trading import DEFAULT_SUPPORTED_SYMBOL_VALUES
from src.shared.utils.symbols import symbol_short

SUPPORTED = DEFAULT_SUPPORTED_SYMBOL_VALUES


@pytest.mark.parametrize(
    ("headline", "expected"),
    [
        ("Bitcoin jumps after CPI as shorts get squeezed", ("BTC/USDT",)),
        ("BTC reclaims $78K after a whipsaw session", ("BTC/USDT",)),
        ("Ether and Solana lead the altcoin rebound", ("ETH/USDT", "SOL/USDT")),
        ("Ripple wins another round against the SEC", ("XRP/USDT",)),
        ("BNB Chain upgrade goes live on mainnet", ("BNB/USDT",)),
        ("Core inflation rose more than expected in August", ()),
    ],
)
def test_supported_coins_are_caught_by_ticker_or_name(headline: str, expected: tuple[str, ...]) -> None:
    assert crypto_symbols_mentioned(headline, SUPPORTED) == expected


@pytest.mark.parametrize(
    "headline",
    ["Solar stocks rally as sol-gel coatings demand rises", "Ethics probe widens at the agency", "Whether rates fall is unclear"],
)
def test_lookalike_words_are_not_coins(headline: str) -> None:
    """Tickers are case-sensitive and word-bounded; names are word-bounded ("ether" is not "whether")."""
    assert crypto_symbols_mentioned(headline, SUPPORTED) == ()


def test_a_coin_added_only_by_configuration_is_still_caught_by_its_ticker() -> None:
    """The "MUST include a new coin" half: no curated name exists for LTC, the ticker still matches."""
    assert crypto_symbols_mentioned("LTC spikes on a spot ETF filing", (*SUPPORTED, "LTC/USDT")) == ("LTC/USDT",)


def test_every_default_supported_coin_has_curated_news_names() -> None:
    """Adding a coin to DEFAULT_SUPPORTED_SYMBOLS without news names fails here, in CI, not in prod."""
    missing = [symbol for symbol in SUPPORTED if symbol_short(symbol) not in CRYPTO_ASSET_NEWS_NAMES]

    assert not missing, f"add news names for {missing} to CRYPTO_ASSET_NEWS_NAMES (src/shared/constants/crypto_news_assets.py)"


def test_coverage_counts_relevant_headlines_and_names_every_supported_coin() -> None:
    """NEWS-2a: the snapshot says which supported coins the news named, zeros included.

    A coin with no news this cycle must still appear (with 0): "the news MUST include it" is only
    checkable if an absent coin is visible, not silently missing from the payload.
    """
    texts = [
        "Bitcoin jumps after CPI as shorts get squeezed",
        "Ether and Solana lead the altcoin rebound",
        "Core inflation rose more than expected in August",
        "Markets wobble into the weekend",
    ]

    coverage = crypto_news_coverage(
        texts,
        source_of={"Markets wobble into the weekend": "CoinDesk"},
        crypto_sources=frozenset({"CoinDesk"}),
        supported_symbols=SUPPORTED,
    )

    assert coverage.n_relevant == 3, "two name a coin, one comes from a crypto newsroom, the CPI line is macro"
    assert coverage.symbol_mentions == {"BTC/USDT": 1, "ETH/USDT": 1, "SOL/USDT": 1, "XRP/USDT": 0, "BNB/USDT": 0}


def test_coverage_counts_a_coin_added_only_by_configuration() -> None:
    coverage = crypto_news_coverage(
        ["LTC spikes on a spot ETF filing"],
        source_of={},
        crypto_sources=frozenset(),
        supported_symbols=(*SUPPORTED, "LTC/USDT"),
    )

    assert coverage.symbol_mentions["LTC/USDT"] == 1
    assert coverage.n_relevant == 1
