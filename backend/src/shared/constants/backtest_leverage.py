"""Backtest linear-perp simulation leverage bounds (aligned with live paper SoT)."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from src.shared.constants.exchanges import MAX_LEVERAGE, MIN_LEVERAGE


class BacktestMarketMode(StrEnum):
    """Optional explicit market_mode on run/compare/hub requests (ADR-013 §6)."""

    SPOT = "spot"
    LINEAR_PERP = "linear_perp"


class PerpAllowedSides(StrEnum):
    """When leverage > 0, which signal directions may open new positions (perp simulation)."""

    BOTH = "both"
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"


class BacktestPerpMmrMode(StrEnum):
    """Perp maintenance margin simulation mode."""

    FLAT = "flat"
    TIERED = "tiered"


def parse_perp_allowed_sides(value: PerpAllowedSides | str | None) -> PerpAllowedSides:
    """Parse persisted/request value, fail-closed to BOTH."""
    if isinstance(value, PerpAllowedSides):
        return value
    if value is None:
        return PerpAllowedSides.BOTH
    try:
        return PerpAllowedSides(str(value).lower().strip())
    except ValueError:
        return PerpAllowedSides.BOTH


def parse_backtest_perp_mmr_mode(value: BacktestPerpMmrMode | str | None) -> BacktestPerpMmrMode:
    """Parse persisted/request value, fail-closed to FLAT."""
    if isinstance(value, BacktestPerpMmrMode):
        return value
    if value is None:
        return BacktestPerpMmrMode.FLAT
    try:
        return BacktestPerpMmrMode(str(value).lower().strip())
    except ValueError:
        return BacktestPerpMmrMode.FLAT


def perp_allowed_sides_to_str(value: PerpAllowedSides | str | None) -> str | None:
    """Normalize for JSON, DB `config`, and compare history equality."""
    if value is None:
        return None
    if isinstance(value, PerpAllowedSides):
        return value.value
    return str(value)


def backtest_market_mode_to_str(value: BacktestMarketMode | str | None) -> str | None:
    """Normalize to primitive for JSON, dataclass DTOs, and equality checks."""
    if value is None:
        return None
    if isinstance(value, BacktestMarketMode):
        return value.value
    return str(value)


# Spot path uses leverage 0. Perp path uses isolated linear math; bounds match paper trading app.
BACKTEST_SPOT_LEVERAGE: Final[int] = 0
BACKTEST_PERP_MIN_LEVERAGE: Final[int] = MIN_LEVERAGE
BACKTEST_PERP_MAX_LEVERAGE: Final[int] = MAX_LEVERAGE

# Simplified USDT-linear isolated model: maintenance as fraction of notional (not exchange-tier tables).
BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE: Final[float] = 0.004
BACKTEST_TIERED_MMR_LOW: Final[float] = 0.004
BACKTEST_TIERED_MMR_HIGH: Final[float] = 0.025
BACKTEST_TIERED_MMR_NOTIONAL_THRESHOLD_USD: Final[float] = 150_000.0

# Exit reason when intrabar low/high crosses simplified isolated liq (engine, chart JSON).
BACKTEST_EXIT_TYPE_LIQUIDATION: Final[str] = "liquidation"

# A stop beyond the liquidation price rests this far inside it: both fire on the mark price, so the stop must be first
# (Lighter: 'a stop-loss with a trigger price worse than the liquidation price will not trigger'). One home for the live
# executor (order_shape.inside_liq, LIQ_GAP) and the backtest that must mimic it (backtester_exit_close_stop).
STOP_INSIDE_LIQUIDATION_GAP: Final[float] = 0.002

# An honest mark-to-market drawdown at or beyond this % means the ACCOUNT WAS WIPED, whatever the
# lane's closing balance says. Grading rule, not simulation input: it lives next to the
# liquidation vocabulary because that is the question it answers.
#
# Shared SoT (owner, 2026-08-14). It was `_LEVERAGE_WIPE_MAX_DD_PCT`, private to
# `registry_leaf_capital_harness` and imported across module boundaries by
# `portfolio_capital_matrix` — a name whose leading underscore told every reader not to depend
# on it while three files did.
LEVERAGE_WIPE_MAX_DD_PCT: Final[float] = 95.0

# The owner's class-account leverage lanes (owner, 2026-10-11: "10x, 20x, 30x, 40x, 50x max", margin 10 % of equity
# each). Every lab grade of a book meant for that account reports these lanes; moved here from ladder87 on 2026-10-13
# (owner: "should be SoT") so a script reads one light constant instead of a lab arm and its twenty imports.
OWNER_COIN_LANES: Final[tuple[int, ...]] = (10, 20, 30, 40, 50)


def owner_lanes_up_to(max_leverage: int | None) -> tuple[int, ...]:
    """The owner's lanes a coin can trade: every one up to its venue's max leverage, plus the max itself (Lighter's SOL:
    10 / 20 / 25x; a 5x coin: 5x alone); all of them when the venue's cap is not known. MOVED from the archived
    books_compare.lanes_on (owner 2026-10-21: the SOL v2 grade's ladder; "on lighter max for sol is 25x")."""
    if max_leverage is None:
        return OWNER_COIN_LANES
    return tuple(sorted({lev for lev in OWNER_COIN_LANES if lev <= max_leverage} | {max_leverage}))


def effective_perp_maintenance_margin_mode(
    requested: BacktestPerpMmrMode | str | None,
    *,
    tiered_mmr_server_allowed: bool,
) -> BacktestPerpMmrMode:
    """Coerce requested mode through server kill-switch (fail-closed to flat)."""
    if requested is None:
        return BacktestPerpMmrMode.FLAT
    resolved = requested if isinstance(requested, BacktestPerpMmrMode) else BacktestPerpMmrMode(str(requested).lower().strip())
    if resolved == BacktestPerpMmrMode.TIERED and not tiered_mmr_server_allowed:
        return BacktestPerpMmrMode.FLAT
    return resolved


def resolve_backtest_linear_mmr(
    notional_usd: float,
    mode: BacktestPerpMmrMode | str | None,
    *,
    tiered_mmr_server_allowed: bool,
) -> float:
    """Resolve maintenance margin rate for linear-perp backtest simulation."""
    effective_mode = effective_perp_maintenance_margin_mode(
        mode,
        tiered_mmr_server_allowed=tiered_mmr_server_allowed,
    )
    if effective_mode == BacktestPerpMmrMode.FLAT:
        return BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE
    if notional_usd <= BACKTEST_TIERED_MMR_NOTIONAL_THRESHOLD_USD:
        return BACKTEST_TIERED_MMR_LOW
    return BACKTEST_TIERED_MMR_HIGH


# Keep the stop comfortably inside the liquidation band (a stop AT the liq price never fills).
_SL_CAP_SAFETY_FACTOR: Final[float] = 0.9


def max_sl_pct_for_leverage(
    leverage: int,
    *,
    mmr: float = BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE,
) -> float | None:
    """Max stop-loss % (percent) that can trigger BEFORE isolated-linear liquidation at ``leverage``.

    Liquidation is an adverse move of ~``(1/leverage - mmr)``; a stop beyond that never fires — the
    position is liquidated first (an 8% stop is fine at 3x but impossible at 100x, ~0.5%). Returns
    that distance x a safety factor, in PERCENT. Returns ``None`` when there is no cap (spot /
    leverage <= 1, where liquidation is not a constraint); returns ``0.0`` when maintenance margin
    alone leaves no room for any stop. SL side only — take-profit is a favorable move, never capped.
    """
    if leverage <= 1:
        return None
    liq_distance_fraction = (1.0 / leverage) - mmr
    if liq_distance_fraction <= 0.0:
        return 0.0
    return liq_distance_fraction * _SL_CAP_SAFETY_FACTOR * 100.0
