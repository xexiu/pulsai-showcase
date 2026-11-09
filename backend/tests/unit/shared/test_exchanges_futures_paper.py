"""Behavior: futures paper eligibility per exchange id (CCXT SoT)."""

from __future__ import annotations

import pytest

from src.shared.constants.exchanges import exchange_supports_futures_paper


@pytest.mark.parametrize(
    ("exchange_id", "expected"),
    [
        ("bitget", True),
        ("BITGET", True),
        ("binance", True),
        ("okx", True),
        ("bybit", True),
        ("coinbase", False),
        ("kraken", False),
        ("unknown", False),
    ],
)
def test_exchange_supports_futures_paper_matches_product_map(exchange_id: str, expected: bool) -> None:
    assert exchange_supports_futures_paper(exchange_id) is expected
