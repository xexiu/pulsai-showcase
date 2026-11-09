"""Perp funding accrual overlay (research instrument) — the cost the engine omits.

WHY this module exists:
``CryptoBacktester`` charges entry/exit fees, slippage and isolated liquidation, but
NOT funding on held perpetual positions. Every perp net is therefore overstated (longs
that pay funding) or understated (shorts that receive it) by the funding flows over the
hold. This module accrues funding AFTER a backtest, as a *decoupled* overlay:

- pure + fully testable; reuses the ``Trade`` model and ``funding_rate_fetcher`` history,
- applying it is opt-in — not applying it leaves nets byte-identical (the charge-funding
  -OFF contract), so the live backtest path and the parallel Phase-4 economics are
  undisturbed,
- it is the instrument for the funding-carry and perp re-baseline gauntlet tiers.

In-engine accrual (a ``charge_funding`` flag threaded through the hot loop) is deferred to
productionization, and only if a perp / carry strategy actually clears Tier 4.

Funding mechanics (linear perp): at each settlement the funding rate is paid by longs to
shorts. A position's funding P&L over (entry, exit] is::

    funding_pnl = -direction * sum(rate_i for settlements in window) * notional

so a long (+1) PAYS positive funding (negative P&L) and a short (-1) RECEIVES it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.ml.backtester_types import Trade

#: (settlement_timestamp, funding_rate) pairs as returned by
#: ``funding_rate_fetcher.fetch_funding_history_timestamped`` (rate is a per-interval
#: fraction, e.g. 0.0001 = 0.01%). Timestamps are expected tz-aware UTC.
FundingSeries = Sequence[tuple[datetime, float]]

_LONG = 1
_SHORT = -1


def funding_pnl_for_position(
    *,
    entry_time: datetime,
    exit_time: datetime,
    direction: int,
    notional: float,
    funding_rates: FundingSeries,
) -> float:
    """Signed funding P&L over (entry_time, exit_time] for one perp position.

    Sums every settlement whose timestamp falls in the half-open window
    ``entry_time < ts <= exit_time`` (a position open at the settlement instant pays/receives)
    and returns ``-direction * sum(rate) * notional``. Long pays positive funding; short
    receives it. Caller must keep all datetimes on the same tz basis.
    """
    if direction not in (_LONG, _SHORT):
        raise ValueError(f"direction must be 1 (long) or -1 (short), got {direction}")
    if notional < 0.0:
        raise ValueError(f"notional must be non-negative, got {notional}")
    if exit_time < entry_time:
        raise ValueError("exit_time must be >= entry_time")
    rate_sum = sum(rate for ts, rate in funding_rates if entry_time < ts <= exit_time)
    return -float(direction) * float(rate_sum) * float(notional)


def _parse_trade_ts(ts: str) -> datetime:
    """Parse a Trade ISO timestamp to tz-aware UTC (naive strings assumed UTC)."""
    parsed = datetime.fromisoformat(ts)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def apply_funding_overlay(trades: Sequence[Trade], funding_rates: FundingSeries) -> list[Trade]:
    """Return copies of ``trades`` with perp funding accrued into ``funding_pnl`` and ``net_pnl``.

    A trade missing entry/exit timestamps — or any call with empty ``funding_rates`` — is
    returned unchanged (``funding_pnl`` 0.0, ``net_pnl`` untouched), so applying an empty
    series is a strict no-op. Input trades are never mutated.
    """
    adjusted: list[Trade] = []
    for trade in trades:
        if not funding_rates or trade.entry_time is None or trade.exit_time is None:
            adjusted.append(trade.model_copy())
            continue
        funding = funding_pnl_for_position(
            entry_time=_parse_trade_ts(trade.entry_time),
            exit_time=_parse_trade_ts(trade.exit_time),
            direction=trade.direction,
            notional=trade.size,
            funding_rates=funding_rates,
        )
        adjusted.append(trade.model_copy(update={"funding_pnl": funding, "net_pnl": trade.net_pnl + funding}))
    return adjusted


def total_funding_pnl(trades: Sequence[Trade]) -> float:
    """Signed sum of accrued funding across ``trades`` (0.0 before the overlay is applied)."""
    return float(sum(trade.funding_pnl for trade in trades))


__all__ = [
    "FundingSeries",
    "apply_funding_overlay",
    "funding_pnl_for_position",
    "total_funding_pnl",
]
