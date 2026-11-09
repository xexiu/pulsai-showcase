"""OrderType SoT regression: one definition in `paper_trading`, re-exported from `exchanges`.

Guards against re-introducing duplicate ``OrderType = Literal["market", "limit"]`` aliases
across the ``shared/constants/`` modules. Canonical home is
``src.shared.constants.paper_trading`` (domain-first — order_type is a trading-order concern,
not a market-structure concern). ``shared.constants.exchanges`` re-exports for backward
compatibility; both import paths MUST resolve to the same Python object.
"""

from __future__ import annotations

from typing import Literal, get_args

from src.shared.constants import exchanges, paper_trading
from src.shared.constants.paper_trading import (
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
    OrderType,
)


def test_order_type_literal_equals_string_constants() -> None:
    """Literal must enumerate exactly the two Final constants — no skew, no extras."""
    assert set(get_args(OrderType)) == {ORDER_TYPE_MARKET, ORDER_TYPE_LIMIT}


def test_order_type_string_constants_are_lowercase_market_limit() -> None:
    """Stability pin: CCXT unified API expects lowercase ``market``/``limit``."""
    assert ORDER_TYPE_MARKET == "market"
    assert ORDER_TYPE_LIMIT == "limit"


def test_order_type_alias_is_literal_market_limit() -> None:
    """OrderType is the canonical type for annotating order-type parameters project-wide."""
    assert OrderType == Literal["market", "limit"]


def test_exchanges_reexports_paper_trading_order_type_symbols() -> None:
    """Single SoT: both import paths must resolve to the exact same object."""
    assert exchanges.OrderType is paper_trading.OrderType
    assert exchanges.ORDER_TYPE_MARKET is paper_trading.ORDER_TYPE_MARKET
    assert exchanges.ORDER_TYPE_LIMIT is paper_trading.ORDER_TYPE_LIMIT
