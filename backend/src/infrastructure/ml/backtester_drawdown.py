"""Honest mark-to-market drawdown — the measurement every leverage claim rests on.

MOVED here VERBATIM from ``backtester_metrics.py``, where it sat beside ``calculate_metrics``.
Doc and ledger references naming ``backtester_metrics.mark_to_market_max_drawdown`` describe this
function; only its module changed, never a line of its body (the move script hashes the block
before and after).

WHY IT IS ITS OWN MODULE. ``backtester_metrics`` assembles a ``BacktestResult`` from a finished
trade list. This function does something categorically different: it re-walks the intrabar price
path and marks every OPEN position at the bar's worst adverse extreme, which is what turns a
flattering closed-trade drawdown into a figure able to say "the account was liquidated". Two
responsibilities in one file also carried it past the 400-line cap (CODING_STANDARDS section 7).

PATTERN: none introduced. This is an SRP split of an existing pure function, not a new
abstraction — naming a pattern here would be decoration (ARCHITECTURE_PATTERNS.md section 9,
"pattern-as-explanation").

LAYER (DDD_PATTERNS.md): infrastructure. Arithmetic over an ML backtest's outputs, holding no
business rule of its own.

REUSE-AUDIT: considered leaving it in ``backtester_metrics.py`` — that is the over-cap file this
split exists to fix. Considered ``backtester_capital.py`` — it sizes positions and applies
leverage to entries, and never walks the bar path. Considered ``quant_metrics.py`` — it holds
Sortino / IC / alpha, statistics over a RETURN SERIES with no notion of an open position or a
liquidation floor. Considered ``src/lib/utils/daily_equity_drawdown.py`` — that measures a LIVE
equity curve from recorded balances, not a backtest's intrabar marks. Nothing is forked: this
function has exactly one definition, here.

@see backtester_metrics.py for the metric assembly that consumes it
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from typing import Final, Protocol

import numpy as np

from src.infrastructure.ml.backtester_types import Trade

logger = logging.getLogger(__name__)


class MarkedTrade(Protocol):
    """What the mark-to-market drawdown reads from a trade -- an engine Trade satisfies it, and so does any record that
    carries these six fields (a stored public backtest's trade, a test's stand-in)."""

    @property
    def entry_candle_index(self) -> int | None: ...
    @property
    def exit_candle_index(self) -> int | None: ...
    @property
    def entry_price(self) -> float: ...
    @property
    def direction(self) -> float: ...
    @property
    def size(self) -> float: ...
    @property
    def net_pnl(self) -> float: ...


def mark_to_market_unavailable_reason(
    trades: Sequence[MarkedTrade],
    low_prices: np.ndarray | None,
    high_prices: np.ndarray | None,
) -> str | None:
    """Why ``mark_to_market_max_drawdown`` would return None, or None when it would succeed.

    THE FALLBACK IS SILENT, AND THAT COST A DAY. When the MTM path is unavailable,
    ``calculate_metrics`` quietly stamps ``bar_close`` and reports the understated closed-trade
    drawdown. Nothing says which of five preconditions failed, so a published leveraged row that
    should carry an honest drawdown carries the flattering one and looks identical to a row that
    legitimately has no intrabar data.

    Measured 2026-09-13 against BOTH environments on the same config (BTC/USDT 1d, leverage 5,
    2025-01-01..2026-07-28): prod and localhost BOTH returned ``bar_close`` with 90 trades and
    byte-identical numbers, which proves the cause is shared code rather than data or deploy --
    and then there was no way to narrow it further from outside the process.

    This function is the narrowing, and it is deliberately a SEPARATE read-only predicate rather
    than a second return value: the drawdown function stays a number-or-None, and the diagnosis
    cannot change what it computes.
    """
    if not trades:
        return "no trades"
    if low_prices is None or high_prices is None:
        missing = [n for n, v in (("low", low_prices), ("high", high_prices)) if v is None]
        return f"no {' and '.join(missing)} price series reached calculate_metrics"
    lows = np.asarray(low_prices, dtype=float)
    highs = np.asarray(high_prices, dtype=float)
    if int(lows.shape[0]) == 0:
        return "the low/high price series are empty"
    if int(highs.shape[0]) != int(lows.shape[0]):
        return f"low/high length mismatch ({lows.shape[0]} vs {highs.shape[0]})"
    for position, trade in enumerate(trades):
        if getattr(trade, "entry_candle_index", None) is None or getattr(trade, "exit_candle_index", None) is None:
            return f"trade {position} is missing entry_candle_index or exit_candle_index"
        if float(trade.entry_price) <= 0.0:
            return f"trade {position} has entry_price {trade.entry_price}"
    return None


def _candle_index(value: int | None) -> int:
    """A trade's candle index once ``mark_to_market_unavailable_reason`` passed: None here is a programming error."""
    if value is None:
        msg = "trade candle index is None after mark_to_market_unavailable_reason passed"
        raise ValueError(msg)
    return value


def position_marks(
    entry: int,
    exit_: int,
    entry_px: float,
    direction: float,
    size: float,
    lows: np.ndarray,
    highs: np.ndarray,
    margin_cap: float | None,
) -> tuple[int, int, np.ndarray, np.ndarray] | None:
    """One open position's unrealized PnL over bars [entry, exit) at each bar's LOW and HIGH -- (first bar, end bar, at the
    lows, at the highs) -- its loss floored at its own margin (notional x ``margin_cap``) under isolated margin; None when
    it is open on no bar. The one marking rule: mark_to_market_max_drawdown and a multi-coin wallet's mark both read it."""
    e0 = max(entry, 0)
    e1 = min(exit_, int(lows.shape[0]))
    if e1 <= e0:
        return None
    unit = direction * size / entry_px
    low_pnl = unit * (lows[e0:e1] - entry_px)
    high_pnl = unit * (highs[e0:e1] - entry_px)
    if margin_cap is not None:
        # Loss floor for THIS position = its margin = notional / leverage.
        floor = -abs(size) * margin_cap
        low_pnl = np.maximum(low_pnl, floor)
        high_pnl = np.maximum(high_pnl, floor)
    return e0, e1, low_pnl, high_pnl


def mark_to_market_max_drawdown(
    trades: Sequence[MarkedTrade],
    low_prices: np.ndarray | None,
    high_prices: np.ndarray | None,
    initial_capital: float,
    leverage: float | None = None,
) -> float | None:
    """Bar-by-bar MARK-TO-MARKET max drawdown at each candle's WORST adverse extreme — the honest
    drawdown at leverage.

    WHY (owner 2026-07-25): the closed-trade DD (``start + cumsum(net_pnl)``) only marks equity at
    trade *exits*. A leveraged position that is deeply underwater mid-hold but exits near flat shows
    ~0 drawdown there -- so a 5x book can report -1.88% while the account actually swung far lower.
    This marks each OPEN position's unrealized PnL at every bar's **worst adverse extreme** — the bar
    **LOW for longs**, the bar **HIGH for shorts** — i.e. the deepest the account sank inside the
    candle. **A drawdown of -100% (-1.0) means the position's worst intrabar excursion wiped the
    account: the liquidation level.** This matches how the trade loop scans bar low/high for
    intrabar liquidation.

    Requires the OHLCV ``low_prices`` + ``high_prices`` series and per-trade candle indices, all
    aligned (``entry_candle_index``/``exit_candle_index`` index into the same series). Returns ``None``
    when unavailable so the caller can fall back to the closed-trade DD (e.g. classic-signal backtests).
    """
    # The preconditions have ONE home, the predicate above; the miss is logged with its reason, never silent.
    reason = mark_to_market_unavailable_reason(trades, low_prices, high_prices)
    if reason is not None or low_prices is None or high_prices is None:
        logger.debug("mark-to-market drawdown unavailable, caller falls back to closed-trade DD: %s", reason)
        return None
    lows = np.asarray(low_prices, dtype=float)
    highs = np.asarray(high_prices, dtype=float)
    n = int(lows.shape[0])
    spans: list[tuple[int, int, float, float, float]] = [
        (_candle_index(t.entry_candle_index), _candle_index(t.exit_candle_index), float(t.entry_price), float(t.direction), float(t.size))
        for t in trades
    ]
    # Realized closed-trade PnL steps in from each trade's exit bar onward: each PnL lands on its exit bar, one
    # cumulative sum carries it forward. It was `realized[x:] += pnl` per trade -- O(bars x trades), 24 % of a 5m
    # cell (PERF-MTM-NUMBA, 2026-10-02); this is O(bars + trades) and equal to 1e-12 (pinned by a test).
    exit_bars = np.clip(np.fromiter((xi for _ei, xi, _px, _dir, _sz in spans), dtype=np.int64, count=len(spans)), 0, n - 1)
    steps = np.zeros(n, dtype=float)
    np.add.at(steps, exit_bars, np.fromiter((float(t.net_pnl) for t in trades), dtype=float, count=len(trades)))
    realized = float(initial_capital) + np.cumsum(steps)
    # Open-position unrealized PnL over [entry, exit); the exit bar is booked as realized above.
    #
    # TWO PHYSICALLY REACHABLE MARKS PER BAR, never a per-position worst case. Price genuinely
    # touches the bar LOW and genuinely touches the bar HIGH — two real instants — so the worst
    # ACHIEVABLE account equity in the bar is the worse of those two whole-book valuations.
    #
    # The previous version marked EACH position at its OWN adverse extreme and summed them, which
    # for a mixed-direction book put price at the low (for the longs) and the high (for the shorts)
    # in the SAME instant. Measured on the fixtures that now pin this: a perfectly hedged book —
    # incapable of losing a cent — reported a drawdown, and at a wide enough bar reported a -100%
    # WIPE. Since `mtm_drawdown_wipe` is a KILL screen, that manufactured false ruin verdicts for
    # any book holding longs and shorts concurrently (any 3-class model with max_open_positions>1).
    # A net-exposure fixture measured -58.0% under the old sum against -30.0% achievable: a 93%
    # overstatement.
    #
    # Single-direction books are unaffected — all longs sink together at the same low, which is
    # simultaneous and real — so this tightens the mixed case only.
    #
    # Still conservative about intrabar PATH: OHLC does not say whether the low or the high came
    # first, so entries/exits within the bar are not sequenced. That remaining slack is on the
    # safe side and is the honest limit of the data.
    # ISOLATED-MARGIN CAP. Under isolated margin a position cannot lose more than its own margin —
    # the trade loop closes it at `liquidation_price_linear_isolated_long/short` long before the
    # mark could exceed that. Without the cap this function values every position linearly with NO
    # lower bound, so concurrent positions can drive the account mark to zero while
    # `liquidation_exits` stays 0. MEASURED 2026-08-17 over 90 artifacts / 888,999 cells: 36,781
    # cells sit at the wipe threshold, 3,174 of them with ZERO liquidations, and 504 of THOSE are
    # PROFITABLE — money suppressed by a drawdown the exchange would never have allowed.
    #
    # `leverage=None` keeps the previous (uncapped) behaviour EXACTLY, so every existing caller and
    # artifact is unchanged until a caller opts in by passing the lane's multiple. Only when the
    # margin is actually known does the cap bind.
    margin_cap: float | None = None
    if leverage is not None and float(leverage) > 0.0:
        margin_cap = 1.0 / float(leverage)

    at_low = realized.copy()
    at_high = realized.copy()
    for ei, xi, entry_px, direction, size in spans:
        marked = position_marks(ei, xi, entry_px, direction, size, lows, highs, margin_cap)
        if marked is None:
            continue
        e0, e1, low_pnl, high_pnl = marked
        at_low[e0:e1] += low_pnl
        at_high[e0:e1] += high_pnl
    equity = np.minimum(at_low, at_high)
    # A real account cannot go below zero (bankruptcy floor). Equity hitting 0 = liquidation-level.
    #
    # THIS IS NOT THE LIQUIDATION RULE, and reading it as one is a mistake already filed once
    # ("the DD liquidates at 0% equity but exchanges use maintenance margin, so it is optimistic").
    # It is an ACCOUNT-equity floor: an account cannot be worth less than nothing. Positions are
    # liquidated by the trade loop at the real maintenance-margin price —
    # `liquidation_price_linear_isolated_long/short` via `merge_planned_exit_with_intrabar_liquidation`,
    # scanned intrabar and filled at the bankruptcy price (the whole margin lost, LIQ-ONE), at
    # BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE = 0.004. Measured 2026-08-12: a 5x long liquidates at
    # 80.40 from an entry of 100 — a -19.60% move, 0.40% of entry EARLIER than a naive
    # full-margin-gone rule would fire. So this floor is conservative-correct, not optimistic.
    equity = np.maximum(equity, 0.0)
    running_max = np.maximum.accumulate(equity)
    drawdown = np.where(running_max > 0, (equity - running_max) / running_max, 0.0)
    return max(float(np.min(drawdown)), -1.0)


#: `Trade.direction` for a long, as that field documents it (``1 = long, -1 = short``).
_LONG: Final = 1

#: Buy-and-hold is marked on a unit notional. A drawdown is a ratio, so the notional cancels; a unit
#: keeps the synthetic position from implying any particular account size.
_BUY_AND_HOLD_UNIT_NOTIONAL: Final = 1.0

#: A hold needs an entry bar and a later exit bar; one bar cannot be held through anything.
_MIN_BARS_TO_HOLD: Final = 2


def buy_and_hold_max_drawdown(
    close_prices: np.ndarray | None,
    low_prices: np.ndarray | None,
    high_prices: np.ndarray | None,
) -> float | None:
    """How far a spot holder of the asset fell over the same bars, measured on the books' own ruler.

    A book's drawdown means little alone. "-42%" reads as alarming until you learn the asset itself
    fell 53% over the same bars -- measured 2026-09-16 on BTC/USDT 1d from 2024-10-22, where exactly
    that book beat buy-and-hold while hurting less. This is the second number.

    It is measured by handing ONE long -- entered at the first close, exited at the last, cost-free
    like ``spot_bh_final`` -- to :func:`mark_to_market_max_drawdown`. The benchmark and the book are
    therefore marked identically (bar LOW while open, realized on the exit bar) and can be read side
    by side; a second drawdown formula would be free to disagree with the first.

    Returns ``None`` when the benchmark cannot be measured -- no prices, a single bar, or an unusable
    entry price -- and never ``0.0``, which would claim the asset did not fall.
    """
    if close_prices is None:
        return None
    closes = np.asarray(close_prices, dtype=float)
    if closes.size < _MIN_BARS_TO_HOLD:
        return None
    entry_price = float(closes[0])
    exit_price = float(closes[-1])
    # The two cases above are ordinary — nothing to hold. These are a DATA defect: the feed handed
    # the benchmark a zero or non-finite close. Same `None` for the caller, but it is said out loud,
    # because a corrupt OHLCV window otherwise reads exactly like an empty one.
    entry_ok = math.isfinite(entry_price) and entry_price > 0.0
    if not entry_ok or not math.isfinite(exit_price):
        logger.warning(
            "buy-and-hold drawdown unmeasurable: unusable close price (entry=%s, exit=%s, bars=%d)",
            entry_price,
            exit_price,
            int(closes.size),
        )
        return None
    pnl = _BUY_AND_HOLD_UNIT_NOTIONAL * (exit_price / entry_price - 1.0)
    held = Trade(
        entry_price=entry_price,
        exit_price=exit_price,
        direction=_LONG,
        size=_BUY_AND_HOLD_UNIT_NOTIONAL,
        entry_fee=0.0,
        exit_fee=0.0,
        slippage_cost=0.0,
        gross_pnl=pnl,
        net_pnl=pnl,
        entry_candle_index=0,
        exit_candle_index=int(closes.size) - 1,
    )
    return mark_to_market_max_drawdown([held], low_prices, high_prices, _BUY_AND_HOLD_UNIT_NOTIONAL)
