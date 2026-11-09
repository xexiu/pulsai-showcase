"""Which supported coins a headline is about, and whether it is crypto news at all (pure domain).

Derived from the supported-symbol SoT rather than a hand-kept coin list: tickers come from the
symbols passed in, so a coin added only by configuration is still caught, and curated names come
from ``CRYPTO_ASSET_NEWS_NAMES``. Owner, 2026-09-11: "If someone/dev adds a new coin/symbol, the
news MUST include it also and catch it."

REUSE-AUDIT: considered src/domain/services/news_macro_router.py (macro keyword routing; its
word-bounded pattern style is reused, the router is not extended: macro routing and coin relevance
feed different decisions) and src/shared/utils/symbols.py::symbol_short (reused for base tickers).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache

from src.shared.constants.crypto_news_assets import CRYPTO_ASSET_NEWS_NAMES, CRYPTO_NEWS_GENERIC_TERMS
from src.shared.utils.symbols import symbol_short

_SYMBOL_PATTERN_CACHE_SIZE = 32


def _word_pattern(term: str, *, ignore_case: bool) -> re.Pattern[str]:
    """``term`` on word boundaries; internal spaces match any run of whitespace."""
    body = r"\s+".join(re.escape(part) for part in term.split())
    return re.compile(rf"\b{body}\b", re.IGNORECASE if ignore_case else 0)


@lru_cache(maxsize=_SYMBOL_PATTERN_CACHE_SIZE)
def _symbol_patterns(symbols: tuple[str, ...]) -> tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]:
    """Per symbol: its ticker (case-sensitive: "SOL" is a coin, "sol" is not) plus its curated names."""
    compiled: list[tuple[str, tuple[re.Pattern[str], ...]]] = []
    for symbol in symbols:
        base = symbol_short(symbol)
        names = CRYPTO_ASSET_NEWS_NAMES.get(base, ())
        patterns = (_word_pattern(base, ignore_case=False), *(_word_pattern(name, ignore_case=True) for name in names))
        compiled.append((symbol, patterns))
    return tuple(compiled)


_GENERIC_PATTERNS: tuple[re.Pattern[str], ...] = tuple(_word_pattern(term, ignore_case=True) for term in CRYPTO_NEWS_GENERIC_TERMS)


def crypto_symbols_mentioned(text: str, supported_symbols: Sequence[str]) -> tuple[str, ...]:
    """Supported symbols the headline names by ticker or curated name, in ``supported_symbols`` order."""
    if not text or not text.strip():
        return ()
    return tuple(symbol for symbol, patterns in _symbol_patterns(tuple(supported_symbols)) if any(pattern.search(text) for pattern in patterns))


def _is_relevant(text: str, *, from_crypto_source: bool, named: tuple[str, ...]) -> bool:
    """The relevance rule given the coins already matched, so a caller needing both runs the coin regexes once."""
    if from_crypto_source:
        return True
    if named:
        return True
    return any(pattern.search(text) for pattern in _GENERIC_PATTERNS)


@dataclass(frozen=True, slots=True)
class CryptoNewsCoverage:
    """How much of one refresh's news is crypto news, and which supported coins it named."""

    n_relevant: int
    symbol_mentions: dict[str, int]
    """Headlines naming each supported symbol, in supported-symbol order; 0 for a coin with no news."""


def crypto_news_coverage(
    texts: Sequence[str],
    *,
    source_of: Mapping[str, str],
    crypto_sources: Collection[str],
    supported_symbols: Sequence[str],
) -> CryptoNewsCoverage:
    """Count crypto-relevant headlines and per-coin mentions for one refresh (NEWS-2a, 2026-09-11).

    A headline counts once per coin it names. ``crypto_sources`` are the feeds whose config categories
    mark them as crypto newsrooms, so their headlines are crypto news even without a coin name. Every
    supported symbol is present in the result, so a coin the news did NOT name shows as 0, not as absent.
    """
    mentions = dict.fromkeys(supported_symbols, 0)
    n_relevant = 0
    for text in texts:
        # ONE coin-regex pass per headline, reused for both answers: it used to run once inside
        # is_crypto_relevant and again for the counts (NEWS-2a-DRY, 2026-09-11).
        named = crypto_symbols_mentioned(text, supported_symbols)
        if _is_relevant(text, from_crypto_source=source_of.get(text) in crypto_sources, named=named):
            n_relevant += 1
        for symbol in named:
            mentions[symbol] += 1
    return CryptoNewsCoverage(n_relevant=n_relevant, symbol_mentions=mentions)
