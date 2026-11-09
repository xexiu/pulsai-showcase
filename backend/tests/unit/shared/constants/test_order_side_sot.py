"""OrderSide SoT regression: one definition, colocated with ORDER_SIDE_* string constants.

Guards against re-introducing duplicate `OrderSide = Literal["buy", "sell"]` aliases across
domain/application/infrastructure layers. If a second alias appears, this test fails at
import-time or assertion-time.
"""

from __future__ import annotations

from typing import Literal, get_args

from src.shared.constants.paper_trading import (
    ORDER_SIDE_BUY,
    ORDER_SIDE_SELL,
    OrderSide,
)


def test_order_side_literal_equals_string_constants() -> None:
    """Literal must enumerate exactly the two Final constants — no skew, no extras."""
    assert set(get_args(OrderSide)) == {ORDER_SIDE_BUY, ORDER_SIDE_SELL}


def test_order_side_string_constants_are_lowercase_buy_sell() -> None:
    """Stability pin: CCXT unified API expects lowercase `buy`/`sell`."""
    assert ORDER_SIDE_BUY == "buy"
    assert ORDER_SIDE_SELL == "sell"


def test_order_side_alias_is_literal_buy_sell() -> None:
    """OrderSide is the canonical type for annotating order-side parameters project-wide."""
    assert OrderSide == Literal["buy", "sell"]
