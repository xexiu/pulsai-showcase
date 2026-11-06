"""
Carry strategy constants (SoT for delta-neutral funding-carry).

WHY a dedicated module?
- Carry loop, paper engine, backtester, and admin routes all need the same
  fee/risk/time constants.
- Single import avoids drift between execution, simulation, and reporting paths.

@see docs/04-structural/CODING_STANDARDS.md - Section 2.0 DON'T REINVENT THE WHEEL
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from src.shared.constants.fees import BITGET_TAKER_FEE

# ── Time ──────────────────────────────────────────────────────────────────────

HOURS_PER_YEAR: Final[float] = 365.0 * 24.0
"""Hours in a calendar year (365 days x 24 h). Used to annualise funding rates."""

# ── Numeric guards ────────────────────────────────────────────────────────────

CARRY_QTY_EPS: Final[float] = 1e-9
# Sub-min-lot dust (e.g. Bitget spot min 1e-6 BTC) — treat as flat for establish/rebalance entry.
CARRY_FLAT_DUST_QTY: Final[float] = 1e-6
"""Quantities below this are treated as zero to avoid division-by-zero on tiny legs."""

# ── Margin / risk defaults ────────────────────────────────────────────────────

CARRY_DEFAULT_MMR: Final[float] = 0.005
"""Default maintenance-margin ratio used when the exchange does not report one (0.5%)."""

CARRY_MAX_LEVERAGE: Final[float] = 20.0
"""Hard ceiling on user-supplied leverage for carry positions."""

# ── Exit policy (funding-edge + liquidation backstop; NO directional TP/SL) ───

CARRY_MIN_FUNDING_APR_TO_HOLD: Final[float] = 0.0
"""Auto-exit when recent funding APR (collected on the short perp) drops to/below this.

A delta-neutral carry has no directional TP/SL — its edge IS the funding it collects. 0.0 = exit
only when funding flips negative (the carry would start PAYING). Raise to require a positive floor
that covers holding cost.
"""

CARRY_EXIT_FUNDING_LOOKBACK_DAYS: Final[int] = 3
"""Lookback (days) of realized funding fetched to gauge the current funding regime for the exit check."""

CARRY_EXIT_FUNDING_LOOKBACK_INTERVALS: Final[int] = 3
"""Most-recent funding settlements averaged into the exit APR (smooths single-print noise)."""

# ── Fee constants ─────────────────────────────────────────────────────────────

CARRY_TAKER_FEE_PCT: Final[float] = BITGET_TAKER_FEE * 100
"""Per-leg taker fee expressed as a PERCENT (0.10%).

Derived from the canonical BITGET_TAKER_FEE (0.001) in fees.py so the two
never drift.  Replaces the paper engine's previous 0.05 hard-coded default.
"""

CARRY_ROUNDTRIP_FEE_PCT: Final[float] = 0.30
"""Aggregate round-trip fee percentage used by the carry backtester (open + close both legs)."""

CARRY_REBALANCE_INTERVAL_MINUTES: Final[int] = 15
"""Celery beat cadence for carry-rebalance-tick (monitoring queue)."""

CARRY_DEPLOY_FRACTION: Final[float] = 0.95
"""Fraction of LIVE account equity the carry deploys each tick (dynamic sizing).

The rebalance tick sizes the carry to the *live* Bitget equity (free USDT + spot base value +
futures equity), not a static capital figure — so a deposit/withdrawal auto-scales the position on
the next tick. The <1.0 buffer leaves headroom for fees + maintenance margin. ``carry_capital_usd``
acts only as an upper safety ceiling on the dynamic figure, never as the target.
"""

CARRY_SPOT_FUNDING_BUFFER_MULTIPLIER: Final[float] = 1.05
"""Headroom on spot USDT needed for establish/rehedge spot buys (fees + rounding)."""

CARRY_SWAP_MARGIN_BUFFER_MULTIPLIER: Final[float] = 1.05
"""Headroom on swap USDT reserved for perp margin on establish."""

CARRY_BITGET_MAX_SPOT_TRANSFER_USD: Final[float] = 50.0
"""Max single swap→spot transfer per tick (Bitget internal transfer)."""

CARRY_WALLET_TRANSFER_ROUNDING_EPS_USD: Final[float] = 0.05
"""Headroom when capping establish capital to wallet USDT (cent rounding + max-transfer ceiling)."""

# ── Idempotent order tagging ──────────────────────────────────────────────────

CARRY_CLIENT_ORDER_ID_PREFIX: Final[str] = "carry"
"""Prefix for the deterministic per-leg ``clientOrderId`` (carry order dedup).

A retried rebalance tick re-derives the SAME id for the same logical leg within a
rebalance window, so the venue returns the existing order instead of double-placing
(Bitget ``clientOid`` / Binance ``newClientOrderId`` via CCXT unified ``clientOrderId``).
"""

CARRY_CLIENT_ORDER_ID_HASH_HEX_CHARS: Final[int] = 24
"""Hex chars of the seed sha256 kept in the leg id. ``carry`` (5) + ``-`` + 24 = 30,
under the strictest integrated venue ceiling (Binance 36) enforced by
``ensure_outbound_ccxt_client_order_id``.
"""

# ── Day-count bounds ──────────────────────────────────────────────────────────

DEFAULT_CARRY_DAYS: Final[int] = 365
"""Default look-back / simulation window in calendar days."""

MIN_CARRY_DAYS: Final[int] = 7
"""Minimum accepted value for carry day-count inputs."""

MAX_CARRY_DAYS: Final[int] = 1095
"""Maximum accepted value for carry day-count inputs (3 years)."""

# ── Venue support ─────────────────────────────────────────────────────────────

CARRY_VENUES: Final[frozenset[str]] = frozenset({"bitget", "binance"})
"""CEX venues that support same-exchange spot+perp carry in PulsAI."""

DEFAULT_CARRY_VENUES_CSV: Final[str] = "binance,bitget,hyperliquid"
"""Default comma-separated venue list for funding-rate query endpoints."""

# ── Adverse-move lookback ─────────────────────────────────────────────────────

CARRY_ADVERSE_LOOKBACK_DAYS: Final[int] = 90
"""Days of funding-rate history used to detect adverse funding regimes."""

# ── Status enums ──────────────────────────────────────────────────────────────


class CarryPositionStatus(StrEnum):
    """Lifecycle of a carry strategy record.

    Canonical definition — import from here; the persistence model re-exports it.
    Values must match CarryPositionModel.status column literals exactly.
    """

    ACTIVE = "active"  # the loop manages this carry
    FLAT = "flat"  # closed; no live legs
    HALTED = "halted"  # operator-stopped; loop skips it


class CarryTickStatus(StrEnum):
    """Result status of a single carry-tick execution.

    Used by the carry task to signal outcomes to the orchestrator/logging layer.
    Note: TaskResultStatus.SKIPPED covers the generic 'skipped' case and is not
    duplicated here.
    """

    IDLE = "idle"
    RAN = "ran"
    HALTED = "halted"
    ERROR = "error"
    KILL_SWITCH = "kill_switch"
    DISABLED = "disabled"
    VENUE_NOT_SUPPORTED = "venue_not_supported"
    NO_CREDENTIALS = "no_credentials"
    NO_HYPERLIQUID_CREDENTIALS = "no_hyperliquid_credentials"  # split-topology perp leg creds missing
    EQUITY_READ_FAILED = "equity_read_failed"  # live balance read failed -> skip (never resize on bad data)
    WALLET_PREFLIGHT_FAILED = "wallet_preflight_failed"
    INSUFFICIENT_FUNDS = "insufficient_funds"
