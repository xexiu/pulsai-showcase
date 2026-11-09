"""
After ``create_order``, fetch venue state via CCXT so we can persist an exchange-aligned snapshot.

CCXT unified: ``fetch_order(id, symbol)`` and (futures) ``fetch_positions([symbol])``.
Best-effort only — reconcile failures must not fail the trade (order already executed).

Flattened API fields combine CCXT unified columns (``entryPrice``, ``marginMode``, ``percentage``,
``maintenanceMarginPercentage``, ``realizedPnl``, …) with Bitget raw ``info`` when needed
(e.g. ``breakEvenPrice``), matching what the Bitget UI often shows.

**Single enrichment entrypoint:** :func:`enrich_reconcile_dict_with_merged_public` attaches
``venue_merged_public`` for DB/API. Call sites include HTTP persist tail
(``order_persist_tail``), WS/materialize imports (``venue_open_order_import``), orphan mirror
bundles (``venue_mirror_swap_orphan_bundle``), and lifecycle merge refresh
(:func:`merge_venue_reconcile_json_for_execution_truth_refresh` in
``paper_trading_venue_reconcile_merge``), which delegates to the same enrich path — parity tests
lock identical ``venue_merged_public`` for the same snapshot dict.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from src.shared.constants.exchanges import MARKET_TYPE_SWAP, MarketType

logger = logging.getLogger(__name__)

_CONTRACT_EPS = 1e-12

# USD-M perp: CCXT/venue sometimes maps a non-price field into ``liquidationPrice`` (huge |value|).
# When absent, Bitget shows "--" (no est. liq. at low risk). Drop garbage so merge can use order hints.
_LIQ_USD_ABS_CEILING = Decimal(100000000)
_LIQ_TO_MARK_RATIO_MAX = Decimal(80)
_LIQ_TO_MARK_RATIO_MIN = Decimal("0.00001")

# GET /trading/orders venue_* strings stored under ``venue_merged_public`` (single SoT with UI).
VENUE_MERGED_PUBLIC_API_FIELD_KEYS: Final[tuple[str, ...]] = (
    "venue_entry_price",
    "venue_mark_price",
    "venue_liquidation_price",
    "venue_initial_margin",
    "venue_unrealized_pnl",
    "venue_breakeven_price",
    "venue_realized_pnl",
    "venue_roe_pct",
    "venue_maintenance_margin_rate",
    "venue_margin_mode",
)


def _decimal_fixed_plain_str(value: Decimal, places: int) -> str:
    """JSON-safe decimal string without scientific notation (aligned with demo_trading_helpers)."""
    quantized = value.quantize(Decimal(10) ** -places)
    fixed = format(quantized, "f")
    if "." in fixed:
        fixed = fixed.rstrip("0").rstrip(".")
    return fixed or "0"


def _normalize_margin_mode_for_api(raw: Any) -> str | None:
    """Map CCXT / Bitget margin mode to ``cross`` | ``isolated`` for API consumers."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in {"cross", "crossed"}:
        return "cross"
    if s == "isolated":
        return "isolated"
    if not s:
        return None
    return str(raw).strip()


def _raw_info_dict(container: dict[str, Any]) -> dict[str, Any]:
    raw = container.get("info")
    return raw if isinstance(raw, dict) else {}


def _venue_metric_dec_str(value: Any, places: int) -> str | None:
    if value is None:
        return None
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        logger.debug("venue metric %r is not a decimal; dropped", value)
        return None
    return _decimal_fixed_plain_str(d, places)


def _breakeven_price_candidates(container: dict[str, Any]) -> list[Any]:
    info = _raw_info_dict(container)
    return [
        info.get("breakEvenPrice"),
        info.get("breakevenPrice"),
        container.get("breakevenPrice"),
    ]


def _liquidation_price_candidates_order(order: dict[str, Any]) -> list[Any]:
    info = _raw_info_dict(order)
    return [
        order.get("liquidationPrice"),
        info.get("liquidationPrice"),
        info.get("liqPx"),
        info.get("liquidation_price"),
    ]


def _liquidation_price_candidates_position(position: dict[str, Any]) -> list[Any]:
    info = _raw_info_dict(position)
    return [
        position.get("liquidationPrice"),
        info.get("liquidationPrice"),
        info.get("liqPx"),
        info.get("liquidation_price"),
    ]


def _mark_hint_decimal(container: dict[str, Any]) -> Decimal | None:
    mp = container.get("markPrice")
    if mp is not None:
        try:
            d = Decimal(str(mp))
        except InvalidOperation, ValueError, TypeError:
            d = None
        if d is not None and d > 0:
            return d
    info = _raw_info_dict(container)
    for key in ("markPrice", "markPx", "marketPrice"):
        raw = info.get(key)
        if raw is None:
            continue
        try:
            d = Decimal(str(raw))
        except InvalidOperation, ValueError, TypeError:
            continue
        if d > 0:
            return d
    return None


def _sanitized_liquidation_price_str(raw: Any, *, mark_hint: Decimal | None) -> str | None:
    """Keep plausible USD-M liquidation levels; drop sentinels and mis-mapped junk."""
    if raw is None:
        return None
    try:
        d = Decimal(str(raw))
    except Exception:
        return None
    if d <= 0:
        return None
    if d > _LIQ_USD_ABS_CEILING:
        return None
    if mark_hint is not None and mark_hint > 0:
        ratio = d / mark_hint
        if ratio > _LIQ_TO_MARK_RATIO_MAX or ratio < _LIQ_TO_MARK_RATIO_MIN:
            return None
    return _decimal_fixed_plain_str(d, 8)


def pick_primary_unified_position(
    positions: list[dict[str, Any]],
    unified_symbol: str,
) -> dict[str, Any] | None:
    """Pick the active leg for *unified_symbol* (non-zero contracts), one-way book."""
    for p in positions:
        if p.get("symbol") != unified_symbol:
            continue
        raw = p.get("contracts")
        if raw is None:
            continue
        try:
            c = abs(float(raw))
        except TypeError, ValueError:
            continue
        if c > _CONTRACT_EPS:
            return p
    return None


def flatten_venue_position_to_public_fields(
    position: dict[str, Any] | None,
) -> dict[str, str | None]:
    """Map CCXT unified position (+ Bitget ``info``) to API string fields (plain decimals, no scientific)."""
    empty: dict[str, str | None] = dict.fromkeys(VENUE_MERGED_PUBLIC_API_FIELD_KEYS, None)
    if not position:
        return empty

    breakeven: str | None = None
    for cand in _breakeven_price_candidates(position):
        breakeven = _venue_metric_dec_str(cand, 8)
        if breakeven is not None:
            break

    mark_dec = _mark_hint_decimal(position)
    liq: str | None = None
    for cand in _liquidation_price_candidates_position(position):
        liq = _sanitized_liquidation_price_str(cand, mark_hint=mark_dec)
        if liq is not None:
            break

    mm_mode = _normalize_margin_mode_for_api(position.get("marginMode"))
    if mm_mode is None:
        mm_mode = _normalize_margin_mode_for_api(_raw_info_dict(position).get("marginMode"))

    return {
        "venue_entry_price": _venue_metric_dec_str(position.get("entryPrice"), 8),
        "venue_mark_price": _venue_metric_dec_str(position.get("markPrice"), 8),
        "venue_liquidation_price": liq,
        "venue_initial_margin": _venue_metric_dec_str(
            position.get("initialMargin") if position.get("initialMargin") is not None else position.get("margin"),
            8,
        ),
        "venue_unrealized_pnl": _venue_metric_dec_str(position.get("unrealizedPnl"), 8),
        "venue_breakeven_price": breakeven,
        "venue_realized_pnl": _venue_metric_dec_str(position.get("realizedPnl"), 8),
        "venue_roe_pct": _venue_metric_dec_str(position.get("percentage"), 8),
        "venue_maintenance_margin_rate": _venue_metric_dec_str(position.get("maintenanceMarginPercentage"), 8),
        "venue_margin_mode": mm_mode,
    }


def flatten_venue_futures_hints_from_ccxt_order(order: dict[str, Any] | None) -> dict[str, str | None]:
    """Best-effort liq / break-even (and mark) parsed from a CCXT **order** dict (e.g. ``fetch_order``).

    Bitget often exposes ``breakEvenPrice`` / ``liquidationPrice`` on the raw
    ``info`` blob attached to the order response while the positions book is
    still catching up — use as a fallback merged with :func:`flatten_venue_position_to_public_fields`.
    """
    empty: dict[str, str | None] = dict.fromkeys(VENUE_MERGED_PUBLIC_API_FIELD_KEYS, None)
    if not order:
        return empty

    info = _raw_info_dict(order)
    mark_dec = _mark_hint_decimal(order)
    mark = _venue_metric_dec_str(order.get("markPrice"), 8)
    if mark is None:
        mark = _venue_metric_dec_str(info.get("markPrice"), 8)

    liq: str | None = None
    for cand in _liquidation_price_candidates_order(order):
        liq = _sanitized_liquidation_price_str(cand, mark_hint=mark_dec)
        if liq is not None:
            break

    breakeven: str | None = None
    for cand in _breakeven_price_candidates(order):
        breakeven = _venue_metric_dec_str(cand, 8)
        if breakeven is not None:
            break

    mm_mode = _normalize_margin_mode_for_api(order.get("marginMode"))
    if mm_mode is None:
        mm_mode = _normalize_margin_mode_for_api(info.get("marginMode"))

    empty["venue_liquidation_price"] = liq
    empty["venue_breakeven_price"] = breakeven
    empty["venue_mark_price"] = mark
    empty["venue_margin_mode"] = mm_mode
    return empty


def merge_venue_public_field_dicts(
    primary: dict[str, str | None],
    fallback: dict[str, str | None],
) -> dict[str, str | None]:
    """Prefer *primary* (position); fill any ``None`` slot from *fallback* (order hints)."""
    return {k: primary[k] if primary[k] is not None else fallback.get(k) for k in VENUE_MERGED_PUBLIC_API_FIELD_KEYS}


def merged_venue_public_from_reconcile_snap(
    snap: dict[str, Any] | None,
    *,
    order_symbol: str,
) -> dict[str, str | None]:
    """Single SoT for GET /trading/orders venue_* strings from persisted reconcile JSON."""
    if not snap:
        return flatten_venue_position_to_public_fields(None)
    raw_positions = snap.get("ccxt_positions")
    positions = raw_positions if isinstance(raw_positions, list) else []
    pos = pick_primary_unified_position(positions, order_symbol)
    pos_flat = flatten_venue_position_to_public_fields(pos)
    raw_order = snap.get("ccxt_order")
    order = raw_order if isinstance(raw_order, dict) else None
    order_flat = flatten_venue_futures_hints_from_ccxt_order(order)
    return merge_venue_public_field_dicts(pos_flat, order_flat)


async def fetch_venue_reconcile_snapshot(
    exchange: Any,
    *,
    unified_symbol: str,
    market_type: MarketType,
    ccxt_order_id: str | None,
) -> dict[str, Any] | None:
    """Return ``{ccxt_order, ccxt_positions}`` for DB storage; ``None`` if nothing could be fetched.

    **Swap / futures:** an empty ``ccxt_positions`` list after a **successful**
    ``fetch_positions`` means the venue book is flat for that symbol query — that
    is valid signal for lifecycle (close Pulsai rows), and must **not** be conflated
    with ``fetch_positions`` failing (exception path leaves this flag false).
    """
    ccxt_order: dict[str, Any] | None = None
    ccxt_positions: list[dict[str, Any]] = []
    swap_positions_fetch_succeeded: bool = False

    if ccxt_order_id:
        try:
            ccxt_order = await exchange.fetch_order(ccxt_order_id, unified_symbol)
        except Exception:
            logger.warning(
                "venue reconcile: fetch_order failed order_id=%s symbol=%s",
                ccxt_order_id,
                unified_symbol,
                exc_info=True,
            )

    if market_type == MARKET_TYPE_SWAP:
        try:
            ccxt_positions = await exchange.fetch_positions([unified_symbol])
            swap_positions_fetch_succeeded = True
        except Exception:
            logger.warning(
                "venue reconcile: fetch_positions failed symbol=%s",
                unified_symbol,
                exc_info=True,
            )

    if ccxt_order is not None or swap_positions_fetch_succeeded:
        return {"ccxt_order": ccxt_order, "ccxt_positions": ccxt_positions}

    return None
