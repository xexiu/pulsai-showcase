"""
Exchange fee constants.

CRITICAL: Fee constants directly impact backtesting accuracy and P&L calculations.

Fee structure:
- Taker fee: Paid when your order executes against existing orders (market orders)
- Maker fee: Paid when your order adds liquidity (limit orders that don't fill immediately)
- Slippage: Price difference between expected and actual execution

WHY centralize this?
- Research scripts historically re-derived ``2*(taker+slip)`` or hard-coded ``0.0010``
- Inconsistent fees lead to unrealistic / incomparable backtest results
- Single source of truth for exchange costs + derived round-trip / turnover charges

@see docs/04-structural/CODING_STANDARDS.md - Section 2.0 DON'T REINVENT THE WHEEL
@see ``src.shared.math.cost_floor.round_trip_cost_fraction`` (same formula, callable form)
"""

from __future__ import annotations

from enum import StrEnum

from src.shared.math.cost_floor import round_trip_cost_fraction


class FeeSchedule(StrEnum):
    """Which fees a run charges (ADR-029 Decision 1). Defined once; the cert engine reads it at ``_run_cell``, the
    user backtest doors (``/backtest/run``, ``/backtest/run-async``) read it off the request (P2-1g, 2026-10-10).

    ``STANDARD`` is every venue's published standard tier -- the only schedule money-standings grades.
    ``ZERO`` is a zero-fee VIP tier: maker, taker AND slippage 0 (``fee_config.ZeroFeeConfigService``).
    In the cert its results are a sensitivity shown beside the standard ones, never a tier: a VIP tier is one
    account's. On a user backtest it is the user's own choice of the schedule they actually pay.
    """

    STANDARD = "standard"
    ZERO = "zero"


def parse_fee_schedule(raw: str | None) -> FeeSchedule:
    """The schedule a door or env var names; unset or blank is ``STANDARD``, anything unknown raises.

    Refusing beats defaulting here: a typo that silently fell back to ``standard`` would publish a
    standard grade from a run the caller believed was a sensitivity, or the reverse.
    """
    text = (raw or "").strip().lower()
    if not text:
        return FeeSchedule.STANDARD
    try:
        return FeeSchedule(text)
    except ValueError:
        valid = ", ".join(member.value for member in FeeSchedule)
        raise ValueError(f"unknown fee schedule {raw!r}; expected one of: {valid}") from None


def fee_schedule_artifact_suffix(schedule: FeeSchedule) -> str:
    """``""`` for ``standard`` -- every existing name stays valid -- else ``__fee_<schedule>``.

    Lives beside FeeSchedule (moved from src/cert/fee_schedule, which re-exports it) because the money ledger reads the
    names the cert engine writes, and the application layer does not import the cert package.
    """
    if schedule is FeeSchedule.STANDARD:
        return ""
    return f"__fee_{schedule.value}"


# ============================================================================
# DEFAULT VALUES (Conservative estimates for backtesting)
# ============================================================================

# Default fee rate for backtesting (0.1% = 0.001)
# WHY 0.1%: Standard taker fee on Binance/Bitget without discounts
DEFAULT_FEE_RATE: float = 0.001

# Default slippage for backtesting (0.03% = 0.0003)
# WHY 0.03%: Matches the runtime backtester profile used across validation
# and report generation for liquid major pairs on supported exchanges.
DEFAULT_SLIPPAGE: float = 0.0003


# ============================================================================
# BINANCE FEE STRUCTURE
# ============================================================================
# Source: https://www.binance.com/en/fee/schedule
# Standard tier (no BNB discount, no VIP level)

BINANCE_TAKER_FEE: float = 0.001  # 0.10%
BINANCE_MAKER_FEE: float = 0.001  # 0.10%

# Derived SoT — import these; do NOT re-paste ``2.0 * (BINANCE_TAKER_FEE + …)``
# or magic ``COST = 0.0010`` in research scripts.
#
# DEFAULT_ROUNDTRIP_COST (26 bps): entry+exit taker+slip — use when the book
# charges a full round-trip once per flip (IC screens, many ``_ROUNDTRIP_COST`` sites).
# DEFAULT_TURNOVER_COST_PER_SIDE (10 bps): charge on ``|Δpos|`` per bar (edge-hunt
# ``net_from_pos`` / ``COST``). A 0→1→0 cycle then costs ~20 bps (no slip).
DEFAULT_ROUNDTRIP_COST: float = round_trip_cost_fraction(BINANCE_TAKER_FEE, DEFAULT_SLIPPAGE)
DEFAULT_TURNOVER_COST_PER_SIDE: float = DEFAULT_FEE_RATE

#: Basis points in one unit of return (1 bp = 0.0001). For APIs that take a cost in bps.
BPS_PER_UNIT: int = 10_000

# Note: paying fees in BNB reduces them by 25% (0.10% -> 0.075% a leg on spot). Not modelled --
# the engine prices the standard tier, which is the conservative read. Written as prose rather
# than commented-out constants: dead code that only a suppression keeps alive is not a record.


# ============================================================================
# BINANCE USDⓈ-M FUTURES (PERPETUAL) FEE STRUCTURE
# ============================================================================
# Source: https://www.binance.com/en/fee/futureFee — USDⓈ-M, Regular User (VIP 0),
# no BNB discount. A PERPETUAL is not spot and is not priced like spot.
#
# WHY THIS EXISTS, measured 2026-09-21. Every leveraged lane in the money engine
# (`perp_3x` … `perp_8x`) was charged the SPOT rate above: 0.10% per leg. That is
# 2x the real futures taker and 5x the real futures maker, on the side of the
# ledger that KILLS books — a perp book pays more in the backtest than it would
# on the exchange, so a marginal money-maker reads as a loss.
#
# The bill is not academic: `btc_usdt_5m/gradient_boosting_clf/v5`, perp_3x,
# 652 trades over six weeks, recorded `total_fees = $3,912` on a $10,000 account
# — 79% of its entire $4,957 loss. At these rates the same trades cost ~$1,956
# (taker) or ~$782 (maker).
BINANCE_FUTURES_TAKER_FEE: float = 0.0005  # 0.050%
BINANCE_FUTURES_MAKER_FEE: float = 0.0002  # 0.020%


# ============================================================================
# BITGET FEE STRUCTURE
# ============================================================================
# Source: https://www.bitget.com/fee
# Standard tier

BITGET_TAKER_FEE: float = 0.001  # 0.10%
BITGET_MAKER_FEE: float = 0.001  # 0.10%

# Bitget USDT-M FUTURES, standard tier. Source: https://www.bitget.com/fee
BITGET_FUTURES_TAKER_FEE: float = 0.0006  # 0.060%
BITGET_FUTURES_MAKER_FEE: float = 0.0002  # 0.020%

# Note: VIP tiers have lower fees, but we use standard for conservative backtesting.
#
# SPOT maker == SPOT taker (0.10%) is CORRECT for Binance/Bitget spot at VIP 0 — it is not a
# copy-paste slip, and a test pins it so nobody "fixes" it into a fake discount. On FUTURES the
# two genuinely differ, which is what makes `use_taker_fees` a real lever there and a no-op here.
