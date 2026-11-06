"""Capital-cert bankruptcy realism — SoT shared with /backtest/run economics.

Prod ``CryptoBacktester`` stops when ``initial + realized_pnl <= 0`` and floors
``final_balance`` / ``total_return`` at ruin. CERT packing must not report fantasy
finals from trade books that continued (or would have continued) after mid-path
ruin — the historical source of leveraged "through ruin" money prints.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BankruptcyDetection:
    """Outcome of scanning a capital-lane trade book for account ruin."""

    account_bankrupt: bool
    ruin_trade_index: int | None
    fantasy_post_ruin_trades: int


def _trade_net_pnl(trade: Any) -> float:
    raw = getattr(trade, "net_pnl", None)
    if raw is None and isinstance(trade, Mapping):
        raw = trade.get("net_pnl")
    try:
        return float(raw or 0.0)
    except TypeError, ValueError:
        return 0.0


#: Artifacts store a full wipe as either -1.0 (fraction) or -100.0 (percent). Values are
#: read on both scales rather than normalised at one call site, because the corpus already
#: contains both spellings and a scale guess is how a real ruin gets read as -1% noise.
_WIPE_FRACTION = -0.999
_WIPE_PERCENT = -99.9
_FRACTION_SCALE_MAX = 1.5


def _is_full_wipe(drawdown: float | None) -> bool:
    """True when a mark-to-market drawdown means the equity path reached zero."""
    if drawdown is None:
        return False
    try:
        value = float(drawdown)
    except TypeError, ValueError:
        return False
    if abs(value) <= _FRACTION_SCALE_MAX:
        return value <= _WIPE_FRACTION
    return value <= _WIPE_PERCENT


def detect_account_bankruptcy(
    *,
    initial_capital: float,
    trades: Sequence[Any],
    final_balance: float | None = None,
    mark_to_market_drawdown: float | None = None,
) -> BankruptcyDetection:
    """Detect mid-path ruin and any trades booked after the account was wiped.

    ``mark_to_market_drawdown`` closes a hole that realized PnL cannot see. This scan walks
    CLOSED trade ``net_pnl``, so an account wiped INTRABAR — exactly what the honest MTM
    drawdown measures — never trips it when the closed book happens to be green. Measured
    2026-08-17: 892 cells across the corpus carried a full-wipe drawdown beside a final
    ABOVE initial with ``account_bankrupt: False``, including a lane published at 3.69x B&H.
    Both numbers cannot be true; the drawdown is the one backed by the price path.
    """
    starting = float(initial_capital)
    if starting <= 0:
        return BankruptcyDetection(account_bankrupt=True, ruin_trade_index=None, fantasy_post_ruin_trades=0)

    running = starting
    ruin_idx: int | None = None
    for index, trade in enumerate(trades):
        running += _trade_net_pnl(trade)
        if running <= 0.0:
            ruin_idx = index
            break

    fantasy = 0
    if ruin_idx is not None:
        fantasy = max(0, len(trades) - ruin_idx - 1)

    wiped_final = final_balance is not None and float(final_balance) <= 0.0
    wiped_path = _is_full_wipe(mark_to_market_drawdown)
    account_bankrupt = ruin_idx is not None or wiped_final or wiped_path
    return BankruptcyDetection(
        account_bankrupt=account_bankrupt,
        ruin_trade_index=ruin_idx,
        fantasy_post_ruin_trades=fantasy,
    )


def apply_bankruptcy_to_capital_lane_row(
    row: Mapping[str, Any],
    *,
    trades: Sequence[Any],
) -> dict[str, Any]:
    """Stamp bankruptcy flags; zero fantasy finals so CERT matches wiped /backtest/run books."""
    out = dict(row)
    initial = float(out.get("initial_capital") or 10_000.0)
    final_raw = out.get("final_balance", out.get("final_capital"))
    try:
        final_balance = float(final_raw) if final_raw is not None else initial
    except TypeError, ValueError:
        final_balance = initial

    drawdown_raw = out.get("max_drawdown", out.get("mtm_max_drawdown"))

    detection = detect_account_bankruptcy(
        initial_capital=initial,
        trades=trades,
        final_balance=final_balance,
        mark_to_market_drawdown=drawdown_raw,
    )
    out["account_bankrupt"] = detection.account_bankrupt
    out["fantasy_post_ruin_trades"] = detection.fantasy_post_ruin_trades
    if detection.ruin_trade_index is not None:
        out["ruin_trade_index"] = detection.ruin_trade_index
    else:
        out.pop("ruin_trade_index", None)

    if not detection.account_bankrupt:
        return out

    # Honest wiped account — same floors as backtester_metrics / prod /backtest/run.
    out["final_capital"] = 0.0
    out["final_balance"] = 0.0
    out["total_return"] = -1.0
    out["return_pct"] = -100.0
    out["net_pnl"] = -initial
    return out


__all__ = [
    "BankruptcyDetection",
    "apply_bankruptcy_to_capital_lane_row",
    "detect_account_bankruptcy",
]
