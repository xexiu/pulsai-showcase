"""
Isolated USDT-linear perp liquidation reference prices (simplified v1).

Pure math — lives under ``shared`` to avoid import cycles (``backtester_trade_math`` must not
pull ``domain.services`` during ``infrastructure.ml`` package init).

ADR-013 §6 documents assumptions vs live venues.

TWO PRICES, ONE POSITION (LIQ-ONE, 2026-10-18): the LIQUIDATION price is where the venue takes the position over --
the bankruptcy price moved toward the entry by the maintenance margin rate -- and the BANKRUPTCY price is where the
isolated margin is used up. The venue closes a liquidated position against the bankruptcy price and keeps any surplus
for its insurance fund, so the trader loses exactly the margin (exchange liquidation docs: Bybit / BingX / Mudrex).
The backtest triggers at the first and fills at the second.

A STOP SET PAST THE LIQUIDATION PRICE (STOP-REST, 2026-11-08) rests STOP_INSIDE_LIQUIDATION_GAP inside it, toward the
entry: both fire on the mark price, so the stop must be first. ``stop_rest_price`` is that price's one home -- read by the
live executor (order_shape.inside_liq), the replay's chart (ModelBookChart), the backtester's hard stop
(backtester_exit_close_stop) and the re-entry grader (k_reentry_grade).
"""

from src.shared.constants.backtest_leverage import STOP_INSIDE_LIQUIDATION_GAP


def stop_rest_price(liquidation: float, side: int) -> float:
    """Where the venue rests a stop the model set past ``liquidation``: STOP_INSIDE_LIQUIDATION_GAP inside it, toward
    the entry (``side`` +1 long: above it; -1 short: below it)."""
    return liquidation * (1 + side * STOP_INSIDE_LIQUIDATION_GAP)


def _check_inputs(entry_price: float, leverage: int) -> None:
    if entry_price <= 0 or leverage < 1:
        msg = "entry_price must be > 0 and leverage >= 1"
        raise ValueError(msg)


def liquidation_price_linear_isolated_long(
    entry_price: float,
    leverage: int,
    maintenance_margin_rate: float,
) -> float:
    """Liquidation (trigger) price of a long: the price falls this far and the venue takes the position over.
    leverage >= 1 required for a sane divisor."""
    _check_inputs(entry_price, leverage)
    return float(entry_price * (1.0 + maintenance_margin_rate - 1.0 / float(leverage)))


def liquidation_price_linear_isolated_short(
    entry_price: float,
    leverage: int,
    maintenance_margin_rate: float,
) -> float:
    """Liquidation (trigger) price of a short: the price rises this far and the venue takes the position over."""
    _check_inputs(entry_price, leverage)
    return float(entry_price * (1.0 - maintenance_margin_rate + 1.0 / float(leverage)))


def bankruptcy_price_linear_isolated(entry_price: float, leverage: int, direction: int) -> float:
    """The price at which an isolated position at ``leverage`` has lost its whole margin -- where a liquidated position
    is closed (``direction`` +1 long, -1 short)."""
    _check_inputs(entry_price, leverage)
    return float(entry_price * (1.0 - (1 if direction > 0 else -1) / float(leverage)))
