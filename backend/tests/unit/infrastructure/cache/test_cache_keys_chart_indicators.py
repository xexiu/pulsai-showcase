"""Tests for ``CacheKeys.chart_indicators_payload`` — J4 supervisor-precompute key.

Pairs with the SoT constants in
``src.shared.constants.chart_indicators_cache``. The key SHAPE must be
the same string everywhere it's used (supervisor writer + handler
reader), so a wrong literal here is a silent J4-miss in prod.
"""

from __future__ import annotations

from src.infrastructure.cache.keys import CacheKeys
from src.shared.constants.chart_indicators_cache import CHART_INDICATORS_PAYLOAD_KEY_PREFIX


def test_chart_indicators_payload_key_uses_sot_prefix() -> None:
    """Key MUST start with the SoT prefix so the writer + reader stay in sync."""
    key = CacheKeys.chart_indicators_payload("binance", "BTC/USDT", "5m")
    assert key.startswith(CHART_INDICATORS_PAYLOAD_KEY_PREFIX)


def test_chart_indicators_payload_normalizes_exchange_to_lowercase() -> None:
    """Mixed-case exchange names MUST collapse to lowercase — sibling to ``ohlcv_exchange_tail``."""
    upper = CacheKeys.chart_indicators_payload("Binance", "BTC/USDT", "5m")
    lower = CacheKeys.chart_indicators_payload("binance", "BTC/USDT", "5m")
    assert upper == lower


def test_chart_indicators_payload_key_includes_symbol_and_timeframe() -> None:
    """Key MUST embed exchange + symbol + timeframe so concurrent (ex, sym, tf) writers don't collide."""
    key = CacheKeys.chart_indicators_payload("binance", "BTC/USDT", "5m")
    # Symbol normalized via ``symbol_to_exchange_namespaced_segment`` like ohlcv_exchange_tail does.
    assert "binance" in key
    assert "BTC_USDT" in key  # exchange-namespaced segment is uppercase + underscore
    assert "5m" in key


def test_chart_indicators_payload_key_distinct_per_timeframe() -> None:
    """Two timeframes for the same (exchange, symbol) MUST produce distinct keys."""
    key_5m = CacheKeys.chart_indicators_payload("binance", "BTC/USDT", "5m")
    key_1h = CacheKeys.chart_indicators_payload("binance", "BTC/USDT", "1h")
    assert key_5m != key_1h


def test_chart_indicators_payload_key_distinct_per_exchange() -> None:
    """Two exchanges for the same (symbol, tf) MUST produce distinct keys (no cross-venue collision)."""
    key_binance = CacheKeys.chart_indicators_payload("binance", "BTC/USDT", "5m")
    key_bitget = CacheKeys.chart_indicators_payload("bitget", "BTC/USDT", "5m")
    assert key_binance != key_bitget
