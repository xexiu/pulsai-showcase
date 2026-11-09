"""Source-of-truth for CCXT ``create_order`` ``params`` dict keys.

Why these live here (P8-M-3 / G-7 remediation):

CCXT's unified API ingests venue-specific behaviour through a free-form
``params`` dict keyed by string literals the exchange expects (see the
CCXT manual at https://docs.ccxt.com/#/?id=create-order — the unified keys
``reduceOnly``, ``stopPrice``, ``stopLoss``, ``takeProfit`` are documented
there, and the venue adapters translate them into their native payloads).

Pre-P8, these literal strings were inlined across multiple call sites
(``binance_futures`` adapter bracket attach, ``ccxt_sltp_orders`` legacy
placer, ``ccxt_bitget_swap_brackets`` composer). A typo in any of those
spells a silent disaster: the venue accepts the order, but without the
expected semantic (no reduce-only -> position flips instead of closes;
no stopPrice -> the trigger never fires). Pinning the keys here makes
any future CCXT spelling drift a one-file change protected by the SoT
regression test (``tests/unit/shared/constants/test_ccxt_params_sot.py``).

Usage: import the specific constant you need — do not import via wildcard.
Import-time cost is zero (module-level ``Final`` string constants).
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "CCXT_PARAM_CLIENT_ORDER_ID",
    "CCXT_PARAM_POSITION_SIDE",
    "CCXT_PARAM_REDUCE_ONLY",
    "CCXT_PARAM_STOP_LOSS",
    "CCXT_PARAM_STOP_LOSS_PRICE",
    "CCXT_PARAM_STOP_PRICE",
    "CCXT_PARAM_TAKE_PROFIT",
    "CCXT_PARAM_TAKE_PROFIT_PRICE",
    "CCXT_PARAM_TRIGGER_PRICE",
    "CCXT_POSITION_SIDE_LONG",
    "CCXT_POSITION_SIDE_SHORT",
]


CCXT_PARAM_POSITION_SIDE: Final[str] = "positionSide"
"""``params["positionSide"]`` — Binance USDS-M hedge mode (paired with side).

See CCXT / Binance unified futures order params.
"""

CCXT_POSITION_SIDE_LONG: Final[str] = "LONG"
"""Hedge-mode close leg for a **sell** that reduces a **long** (CCXT unified)."""

CCXT_POSITION_SIDE_SHORT: Final[str] = "SHORT"
"""Hedge-mode close leg for a **buy** that reduces a **short** (CCXT unified)."""

CCXT_PARAM_REDUCE_ONLY: Final[str] = "reduceOnly"
"""``params["reduceOnly"] = True`` — the order can only shrink the position.

Used for SL / TP follow-up orders on Binance USDT-M futures. Bitget futures
also respects it for reduce-only market closes.
"""

CCXT_PARAM_STOP_PRICE: Final[str] = "stopPrice"
"""``params["stopPrice"] = <decimal>`` — trigger price for a STOP / STOP_MARKET
order at most venues (Binance USDT-M uses it on
``STOP_MARKET`` / ``TAKE_PROFIT_MARKET`` order types).
"""

CCXT_PARAM_STOP_LOSS: Final[str] = "stopLoss"
"""``params["stopLoss"] = {"triggerPrice": <decimal>}`` — Bitget's preset-SL
shape on ``create_order``. Binance USDT-M does NOT support this key on
``create_order`` (see ``binance_futures`` adapter docstring) — brackets
are placed as separate STOP_MARKET orders there.
"""

CCXT_PARAM_TAKE_PROFIT: Final[str] = "takeProfit"
"""``params["takeProfit"] = {"triggerPrice": <decimal>}`` — Bitget's preset-TP
shape on ``create_order`` (same caveat as ``CCXT_PARAM_STOP_LOSS``).
"""

CCXT_PARAM_TRIGGER_PRICE: Final[str] = "triggerPrice"
"""Sub-key under ``stopLoss`` / ``takeProfit`` for Bitget's preset brackets.

``{"stopLoss": {"triggerPrice": 70000.0}}`` is the unified Bitget shape; see
``src.domain.services.ccxt_bitget_swap_brackets.build_bitget_swap_bracket_params``
for the composer that produces it.
"""

CCXT_PARAM_STOP_LOSS_PRICE: Final[str] = "stopLossPrice"
"""``params["stopLossPrice"] = <decimal>`` — unified CCXT trigger-attached SL
shorthand used by some venues (Bybit, Kraken futures). Distinct from the
nested ``stopLoss`` dict Bitget uses. Consumed by
``src.infrastructure.exchange.ccxt_sltp_orders.place_exchange_stop_loss``.
"""

CCXT_PARAM_TAKE_PROFIT_PRICE: Final[str] = "takeProfitPrice"
"""``params["takeProfitPrice"] = <decimal>`` — counterpart to
:data:`CCXT_PARAM_STOP_LOSS_PRICE`. Consumed by
``src.infrastructure.exchange.ccxt_sltp_orders.place_exchange_take_profit``.
"""

CCXT_PARAM_CLIENT_ORDER_ID: Final[str] = "clientOrderId"
"""``params["clientOrderId"] = <str>`` — user-supplied idempotent order tag
the venue echoes back on ``fetch_order``. Used across the paper-trading SL /
TP placer so the lifecycle sync can correlate the venue order back to the
originating PulsAI order without relying on the server-side id.
"""
