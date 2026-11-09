"""Turn a CONTINUOUS per-bar return series into a levered capital curve.

The missing primitive between the two capital harnesses this repo already has:

* ``CryptoBacktester`` simulates DISCRETE trades (entry, TP/SL, holding) — the right tool
  for a directional signal, and structurally unable to price a book that has no entries.
* ``funding_ml_carry_portfolio_backtest.simulate_portfolio_equity`` does continuous MTM
  compounding with leverage and ruin — but only for a multi-coin ledger keyed by
  ``weights_json`` / ``fund_gross`` / ``price_gross``, so a single-series book cannot use it.

A short-variance book (``standing_vrp_always``) is continuous and single-series, so it fell
between them: ``cert_registry_leaves_capital.py`` returns ``inapplicable_vrp_venue`` and its
money outcome went uncomputed while it sat ``production_promoted`` in front of users.

This is that shared middle, extracted rather than forked. It takes the net per-bar return of
ANY book and answers the only questions the money gate asks: what did $10k become, how deep
did it actually go on the way, and did the user get wiped out.

Honesty properties, each of which a past corpus bug violated:

* **Leverage scales the PATH, not the result.** ``cap *= 1 + L*r`` per bar. Multiplying a
  final unlevered number by L is the fantasy that hides every drawdown the path went through.
* **Drawdown is marked EVERY bar.** A book that halves and recovers reports its pit, not the
  flat endpoint — the closed-trade-DD artifact that produced the retired "$1M @5x" headlines.
* **Ruin is terminal.** Once equity hits zero the account is liquidated and later bars are
  skipped and counted; no post-ruin recovery is simulated (``fantasy_post_ruin_trades``).
* **Non-finite input is refused.** A NaN bar silently treated as 0% is how a data gap
  flatters a book.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pandas is only needed for the annotation — keep the domain import light
    import pandas as pd


from src.domain.services.edge_lifecycle.capital_cert_headline import (
    CELL_FIELD_LIQUIDATION_EXITS,
    CELL_FIELD_MAX_DRAWDOWN,
    DRAWDOWN_WIPE_THRESHOLD,
)


def _resolve_bar_costs(
    returns: pd.Series,
    cost_per_bar: float,
    costs_per_bar: Sequence[float] | None,
) -> list[float] | None:
    """Validate the cost inputs and return one cost per bar, or None when there is no cost.

    Refuses a short series rather than padding it: padding charges ZERO on the tail, which is a
    silent discount on real bars and would flatter exactly the high-leverage cells that need the
    cost most. Refuses a scalar and a series together, because picking a winner silently drops
    one of two costs the caller believed it was charging.
    """
    if costs_per_bar is None:
        return None

    if cost_per_bar:
        msg = "pass either cost_per_bar or costs_per_bar, not both — two costs is an ambiguity, and silently dropping one understates the book."
        raise ValueError(msg)

    costs = [float(c) for c in costs_per_bar]
    if len(costs) != len(returns):
        msg = f"costs_per_bar has {len(costs)} entries for {len(returns)} bars — refusing to pad, which would charge nothing on the uncovered bars."
        raise ValueError(msg)

    if any(not math.isfinite(c) for c in costs):
        msg = "non-finite value in costs_per_bar — a data gap must not silently become a free bar."
        raise ValueError(msg)

    return costs


def simulate_levered_return_book(
    returns: pd.Series,
    *,
    initial_capital: float,
    leverage: float,
    cost_per_bar: float = 0.0,
    costs_per_bar: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Compound ``returns`` at ``leverage`` and report the honest capital outcome.

    ``cost_per_bar`` is charged on the LEVERED notional (``L * cost``), matching how fees
    accrue on the position actually held rather than on the equity behind it.

    ``costs_per_bar`` is the same charge as a PER-BAR SERIES, for costs that vary and can change
    sign. Perpetual funding is both: it is re-quoted every interval, and a SHORT position
    RECEIVES it. POSITIVE costs the book, NEGATIVE credits it.

    MEASURED on BTC 2021-01-01..2026-08-13 (6,151 intervals, mean +0.000298/day, positive 85.8%
    of the time): over 1,969 days at 8x, funding alone is worth x0.0091 to a long book and
    x108.08 to a short one. A scalar cannot express that, which is why every lane cert in this
    corpus reports ``cost_per_bar: 0.0`` and omits the largest term in its own outcome.

    The series is NOT averaged before use — compounding is path-dependent, so the mean of a real
    funding series is a different book from the series itself.
    """
    bar_costs = _resolve_bar_costs(returns, cost_per_bar, costs_per_bar)

    capital = float(initial_capital)
    peak = capital
    max_dd = 0.0
    liquidated = False
    skipped = 0
    bars = 0

    for index, value in enumerate(returns.to_numpy() if len(returns) else []):
        bar_return = float(value)
        if not math.isfinite(bar_return):
            msg = "non-finite return in the book series — refusing to treat it as a flat bar; a data gap must not silently flatter the capital curve."
            raise ValueError(msg)
        if liquidated:
            skipped += 1
            continue

        bars += 1
        capital *= 1.0 + leverage * bar_return
        bar_cost = bar_costs[index] if bar_costs is not None else float(cost_per_bar)
        if bar_cost:
            capital *= 1.0 - leverage * bar_cost

        if capital <= 0.0:
            capital = 0.0
            liquidated = True

        peak = max(peak, capital)
        if peak > 0.0:
            drawdown = (peak - capital) / peak
            max_dd = max(max_dd, drawdown)
            # RUIN IS TERMINAL, and the line is the one the SCREEN already judges by.
            #
            # `capital <= 0.0` alone only catches a SINGLE bar with `leverage * r <= -1`. Under
            # constant-leverage rebalancing a run of merely-terrible bars drives equity to a tiny
            # positive fraction instead, and multiplicative compounding then runs from there for
            # thousands of bars. Measured on `hunt_vt17_short_mom_ic_4h` (confirm/OOS
            # 2019-01-01..2026-08-01, 16,610 bars): the perp_3x lane reported **$60,995,315 from
            # $10,000 beside a -99.92% drawdown**, and one leverage notch down reported $24,040.
            #
            # The arithmetic was self-consistent; the PRODUCT was not. It assumed infinitely
            # divisible capital, no minimum order size, and an account holding fractions of a cent
            # trading its way back to $61M. The physically correct floor is the venue minimum
            # notional, but that is reported per-symbol by the exchange
            # (`order_preflight.enforce_min_notional`) and is unavailable to an offline return
            # book — so this uses the one in-repo definition of "the account is gone",
            # `DRAWDOWN_WIPE_THRESHOLD`, which `headline_exclusion_reason` already screens on.
            # Simulating ruin and judging ruin now use the SAME line, instead of an engine
            # manufacturing numbers its own screen throws away.
            #
            # The drawdown is then 100%: the account is gone, matching
            # `mark_to_market_max_drawdown`'s documented "-1.0 means ... the liquidation level".
            if not liquidated and -drawdown <= DRAWDOWN_WIPE_THRESHOLD:
                capital = 0.0
                liquidated = True
                max_dd = 1.0

    return {
        "initial_capital": round(float(initial_capital), 2),
        "final_capital": round(capital, 2),
        # The SoT ruin screen (`capital_cert_headline`) reads THESE two spellings, and a drawdown
        # as a FRACTION. Both values already exist above, so they are emitted rather than
        # re-derived: converting `max_drawdown_pct` back by /100 downstream would reintroduce a
        # magic number and a rounding step for a number we are holding exactly.
        CELL_FIELD_LIQUIDATION_EXITS: 1 if liquidated else 0,
        CELL_FIELD_MAX_DRAWDOWN: round(-max_dd, 6),
        "total_return_pct": round((capital / float(initial_capital) - 1.0) * 100.0, 4) if initial_capital else 0.0,
        "max_drawdown_pct": round(-max_dd * 100.0, 4),
        "account_liquidated": liquidated,
        "leverage": leverage,
        "n_bars": bars,
        "bars_after_ruin_skipped": skipped,
    }


__all__ = ["simulate_levered_return_book"]
