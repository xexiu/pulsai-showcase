"""Tests for Coinglass shared constants."""

from __future__ import annotations

from src.shared.constants.coinglass import (
    COINGLASS_API_MAX_LIMIT,
    COINGLASS_CROSS_VENUE_EXCHANGES,
    COINGLASS_DEFAULT_BASE_URL,
    COINGLASS_DEFAULT_EXCHANGE,
    COINGLASS_HTTP_MAX_RETRIES,
)


def test_coinglass_default_exchange_is_binance_label() -> None:
    assert COINGLASS_DEFAULT_EXCHANGE == "Binance"


def test_cross_venue_exchanges_includes_primary_venues() -> None:
    assert "Binance" in COINGLASS_CROSS_VENUE_EXCHANGES
    assert "Bybit" in COINGLASS_CROSS_VENUE_EXCHANGES


def test_client_defaults_are_centralized() -> None:
    assert COINGLASS_DEFAULT_BASE_URL.startswith("https://")
    assert COINGLASS_API_MAX_LIMIT == 1000
    assert COINGLASS_HTTP_MAX_RETRIES >= 1
