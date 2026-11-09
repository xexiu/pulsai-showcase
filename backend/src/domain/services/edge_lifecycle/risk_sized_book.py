"""The risk-sized money grade (P1-0): every trade risks a fixed fraction of CURRENT equity, isolated margin per lane.

IMPORTERS/CALLERS: research/edge_hunt/loop_contract_cert.apply_risk_sized_lane_certs (the door's money pass) and
cert/risk_sized_trades.stance_trades (which builds the RiskTrade records). AFFECTED API: none.
DATA SCHEMAS: a cell's capital_backtest gains `risk_sized_cert` (RiskSizedCert) -- harness `risk_sized_book`, one
lane per leverage (RiskSizedLane) in the return-book dialect the ruin screen already reads (final_capital,
max_drawdown_pct, liquidation_exits, account_liquidated, account_bankrupt), so the money decision grades it with no
second reader.

WHY (owner, 2026-10-04): "$20 capital, only $2 risk, 50x, thin SL, TP ladder, BE after TP2 -- ALL-IN is another
case". The door's grade was levered_return_book only: the WHOLE account at L x on every bar. That is the all-in
case and stays beside this one as the disclosure, never instead of it. Here a trade's notional is
`risk_fraction x equity / stop distance`, capped at `leverage x equity` (an isolated position cannot post more
margin than the account holds), so a stop-out costs the risk and a win compounds on the equity it left behind.

LIQUIDATION is the engine's: an isolated linear perp is liquidated `1/L - MMR` away from entry
(shared/math/linear_isolated_perp, the flat BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE). A trade whose adverse move
reached that distance while open is liquidated and loses its MARGIN -- whether its stop sat beyond the liquidation
price or a gap jumped the stop -- and the loss stops at the margin: that is what isolated means. Any liquidation
excludes the lane through the ruin screen (liquidation-clean is a hard headline filter in this repo).

REUSE-AUDIT: considered return_book_capital_cert.certify_return_book_lanes (the lane loop, the ruin screen call
and lane_name are reused; its per-bar compounding of a return SERIES is exactly what this replaces for a
trade-sized book); backtester_trade_math's liquidation merge (needs the engine's position objects, not one trade's
summary); linear_isolated_perp (reused, the liquidation distance).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, NotRequired, TypedDict

from src.domain.services.edge_lifecycle.capital_cert_headline import (
    headline_exclusion_reason,
    is_ruin_reason,
)
from src.domain.services.edge_lifecycle.return_book_capital_cert import lane_name
from src.shared.constants.backtest_leverage import BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE
from src.shared.constants.capital_cert_harness import CAPITAL_CERT_HARNESS_RISK_SIZED_BOOK
from src.shared.math.linear_isolated_perp import liquidation_price_linear_isolated_long

#: Where a cell's capital_backtest stores its RiskSizedCert -- the money grade when the cell declares its stance;
#: ``leverage_cert`` (all-in) rides beside it as the disclosure (owner, 2026-10-04).
CELL_FIELD_RISK_SIZED_CERT: Final = "risk_sized_cert"
#: A lane at or below 1x is the spot account: no shorting, no liquidation, notional capped at the equity.
SPOT_LEVERAGE: Final[float] = 1.0
#: Sub-cent precision: the owner's own book is $20, where a cent is 0.05% of the account.
_CAPITAL_DECIMALS: Final[int] = 6
_PERCENT: Final[float] = 100.0
_SIZING: Final[str] = "risk_fraction_of_current_equity"


@dataclass(frozen=True)
class RiskTrade:
    """One closed trade, per unit of notional.

    side: +1 long, -1 short. stop_frac: entry-to-stop distance / entry price (> 0). net_return: the whole
    position's realised return after its target parts, costs and funding. worst_adverse: the deepest move against
    the entry while the position was open (>= 0) -- what the drawdown and the liquidation check read.
    """

    side: int
    stop_frac: float
    net_return: float
    worst_adverse: float
    #: The bars the trade filled and exited on, when the walk that built it knew them (stance_trades does) -- -1 when
    #: not. Carried for a chart of the book; the money never reads them.
    entry_bar: int = -1
    exit_bar: int = -1


class RiskSizedLane(TypedDict):
    """One lane's outcome. The field names ARE the ruin screen's (headline_exclusion_reason reads them)."""

    initial_capital: float
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    liquidation_exits: int
    account_liquidated: bool
    account_bankrupt: bool
    leverage: float
    risk_fraction: float
    num_trades: int
    n_skipped_shorts: int
    trades_after_ruin_skipped: int
    ruin_reason: NotRequired[str | None]


class RiskSizedCert(TypedDict):
    """The whole ladder: every lane, the ones that liquidated and the highest lane that stayed clean."""

    harness: str
    sizing: str
    risk_fraction: float
    lanes: dict[str, RiskSizedLane]
    liquidated_lanes: list[str]
    max_clean_leverage_survived: float | None
    num_trades: int
    # What the builder that walked the trades stamps beside them (cert/risk_sized_ladder): the round trip charged,
    # whether funding was, why not, the same-window buy-and-hold, and why a ladder holds no lanes.
    cost_bps_round_trip: NotRequired[float]
    funding_modelled: NotRequired[bool]
    funding_reason: NotRequired[str]
    spot_bh_final: NotRequired[float | None]
    skipped_reason: NotRequired[str]


def liquidation_distance(leverage: float, maintenance_margin_rate: float = BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE) -> float:
    """The adverse move, as a fraction of entry, that liquidates an isolated position at ``leverage`` -- at the
    backtest's flat maintenance rate unless a venue's own is given (LIGHTER-LIMITS: Lighter's SOL keeps 2.4 %)."""
    return 1.0 - liquidation_price_linear_isolated_long(1.0, int(leverage), maintenance_margin_rate)


def risk_sized_notional(equity: float, stop_frac: float, *, leverage: float, risk_fraction: float) -> float:
    """The notional one trade takes: ``risk_fraction`` of ``equity`` lost if its stop (``stop_frac`` of the entry) is
    hit, capped at what the lane can post -- ``leverage`` x equity, or the equity itself on spot (BACKTEST-ONE S2b:
    the ONE sizing rule, walked here and called by the engine's ``risk_sized`` mode)."""
    lane_leverage = SPOT_LEVERAGE if leverage <= SPOT_LEVERAGE else float(leverage)
    return min(risk_fraction * equity / stop_frac, lane_leverage * equity)


def _validate(trades: Sequence[RiskTrade], risk_fraction: float) -> None:
    if not 0.0 < risk_fraction <= 1.0:
        msg = f"risk_fraction must be in (0, 1], got {risk_fraction}"
        raise ValueError(msg)
    for trade in trades:
        if trade.stop_frac <= 0.0:
            msg = f"stop_frac must be positive -- a trade without a stop has no risk to size, got {trade.stop_frac}"
            raise ValueError(msg)


def simulate_risk_sized_lane(
    trades: Sequence[RiskTrade],
    *,
    initial_capital: float,
    leverage: float,
    risk_fraction: float,
    equity_after: list[float] | None = None,
) -> RiskSizedLane:
    """Walk ``trades`` in order on one lane, each sized at ``risk_fraction`` of the equity before it.

    ``equity_after``, when given, receives the equity after every trade in ``trades`` (one per trade; a skipped one
    carries the equity it found) -- a chart's line is this walk, never a second copy of the sizing rule."""
    _validate(trades, risk_fraction)
    is_spot = leverage <= SPOT_LEVERAGE
    lane_leverage = SPOT_LEVERAGE if is_spot else float(leverage)
    liq_distance = 0.0 if is_spot else liquidation_distance(leverage)
    equity = float(initial_capital)
    peak = equity
    max_drawdown = 0.0
    liquidations = 0
    taken = 0
    skipped_shorts = 0
    after_ruin = 0
    bankrupt = False

    for trade in trades:
        if equity_after is not None and (bankrupt or (is_spot and trade.side < 0)):
            equity_after.append(equity)
        if bankrupt:
            after_ruin += 1
            continue
        if is_spot and trade.side < 0:
            skipped_shorts += 1
            continue
        notional = risk_sized_notional(equity, trade.stop_frac, leverage=leverage, risk_fraction=risk_fraction)
        margin = notional / lane_leverage
        liquidated = not is_spot and trade.worst_adverse >= liq_distance
        if liquidated:
            liquidations += 1
            trough = equity - margin
            pnl = -margin
        else:
            trough = equity - notional * trade.worst_adverse
            pnl = notional * trade.net_return
        max_drawdown = max(max_drawdown, (peak - trough) / peak)
        equity = max(equity + pnl, 0.0)
        peak = max(peak, equity)
        taken += 1
        if equity_after is not None:
            equity_after.append(equity)
        if equity <= 0.0:
            bankrupt = True

    return RiskSizedLane(
        initial_capital=round(float(initial_capital), _CAPITAL_DECIMALS),
        final_capital=round(equity, _CAPITAL_DECIMALS),
        total_return_pct=round((equity / float(initial_capital) - 1.0) * _PERCENT, 4),
        max_drawdown_pct=round(-max_drawdown * _PERCENT, 4),
        liquidation_exits=liquidations,
        account_liquidated=liquidations > 0,
        account_bankrupt=bankrupt,
        leverage=leverage,
        risk_fraction=risk_fraction,
        num_trades=taken,
        n_skipped_shorts=skipped_shorts,
        trades_after_ruin_skipped=after_ruin,
    )


def certify_risk_sized_lanes(
    trades: Sequence[RiskTrade],
    *,
    initial_capital: float,
    leverages: Sequence[float],
    risk_fraction: float,
) -> RiskSizedCert:
    """Every lane's risk-sized outcome, its ruin reason, the liquidated lanes and the highest clean lane."""
    lanes: dict[str, RiskSizedLane] = {}
    liquidated: list[str] = []
    max_clean: float | None = None
    for leverage in sorted(float(lev) for lev in leverages):
        outcome = simulate_risk_sized_lane(trades, initial_capital=initial_capital, leverage=leverage, risk_fraction=risk_fraction)
        ruin_reason = headline_exclusion_reason(outcome)
        outcome["ruin_reason"] = ruin_reason
        key = lane_name(leverage)
        lanes[key] = outcome
        if outcome["account_liquidated"]:
            liquidated.append(key)
        if not is_ruin_reason(ruin_reason):
            max_clean = leverage if max_clean is None else max(max_clean, leverage)

    survived: float | None = None
    if max_clean is not None:
        survived = int(max_clean) if float(max_clean).is_integer() else max_clean
    return RiskSizedCert(
        harness=CAPITAL_CERT_HARNESS_RISK_SIZED_BOOK,
        sizing=_SIZING,
        risk_fraction=risk_fraction,
        lanes=lanes,
        liquidated_lanes=liquidated,
        max_clean_leverage_survived=survived,
        num_trades=len(trades),
    )


def risk_sized_ladder_lanes(holder: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    """The lanes of the risk-sized ladder ``holder`` carries under CELL_FIELD_RISK_SIZED_CERT -- {} when it carries
    none, or carries one with no lanes (a skipped ladder states its reason and grades nothing)."""
    ladder = holder.get(CELL_FIELD_RISK_SIZED_CERT)
    if not isinstance(ladder, Mapping):
        return {}
    lanes = ladder.get("lanes")
    if not isinstance(lanes, Mapping):
        return {}
    return {str(name): lane for name, lane in lanes.items() if isinstance(lane, Mapping)}


__all__ = [
    "CELL_FIELD_RISK_SIZED_CERT",
    "SPOT_LEVERAGE",
    "RiskSizedCert",
    "RiskSizedLane",
    "RiskTrade",
    "certify_risk_sized_lanes",
    "risk_sized_ladder_lanes",
    "risk_sized_notional",
    "simulate_risk_sized_lane",
]
