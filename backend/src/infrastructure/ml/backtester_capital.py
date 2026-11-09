"""Capital & position-management helpers extracted from CryptoBacktester."""

from __future__ import annotations

from src.shared.constants.backtest_leverage import PerpAllowedSides


def calculate_position_sizing(
    position_size: float | None,
    initial_capital: float | None,
    max_open_positions: int | None,
) -> tuple[float, float, bool]:
    """
    Calculate position_size and initial_capital based on inputs.

    INDUSTRY STANDARD FORMULA (AmiBroker, VectorBT):
    position_size = initial_capital / max_open_positions

    Returns:
        tuple of (position_size, initial_capital, sizing_follows_capital). The third is True only
        when the size was DERIVED from the account (Case 2): "all-in" or "1/N of it" shrinks with
        the account, while an explicit position_size is a fixed order (ENGINE-FREEZE-1, see
        `entry_scale_for_free_margin`).
    """
    legacy_default_position_size = 1000.0

    # Case 1: Explicit position_size provided — use it
    if position_size is not None:
        capital = initial_capital if initial_capital is not None else position_size
        return position_size, capital, False

    # Case 2: initial_capital provided, auto-calculate position_size
    if initial_capital is not None:
        calculated_size = (
            initial_capital / max_open_positions if max_open_positions is not None and max_open_positions > 0 else initial_capital * 0.10
        )
        return calculated_size, initial_capital, True

    # Case 3: Neither provided — legacy behavior
    return legacy_default_position_size, legacy_default_position_size, False


def process_closed_positions(
    current_candle: int,
    open_positions: list[tuple[int, float, float]],
    available_balance: float,
    *,
    realistic_mode: bool,
) -> tuple[list[tuple[int, float, float]], float]:
    """
    Process closed positions and return capital.

    REALISTIC MODE returns locked capital when positions close.
    Legacy mode just filters out closed positions.

    Returns:
        (updated_open_positions, updated_available_balance)
    """
    if realistic_mode:
        closed = [pos for pos in open_positions if pos[0] <= current_candle]
        for _exit_candle, locked_collateral, _notional in closed:
            available_balance += locked_collateral
        open_positions = [pos for pos in open_positions if pos[0] > current_candle]
    else:
        open_positions = [pos for pos in open_positions if pos[0] > current_candle]

    return open_positions, available_balance


def free_margin_balance(
    initial_capital: float,
    realized_pnl: float,
    open_positions: list[tuple[int, float, float]],
) -> float:
    """Free (unposted) balance, DERIVED from the account identity rather than accumulated.

    THE DEFECT THIS REPLACES, measured on the real engine (perp_8x, 10 max open, 54 trades):
    three entries were funded from an ``available_balance`` of $1,000 while the account held
    $718, $434 and $153. ``process_closed_positions`` credits back the FULL original margin
    when a position closes, whatever the trade did, and realized PnL never reached the balance
    at all -- it accumulated in a separate field the capital check never read. So the book kept
    posting full margin after the account had lost the money.

    That is where ``max_drawdown -1.0`` beside ``liquidation_exits 0`` comes from. Neither
    instrument is wrong: driven directly, the mark reads -0.96 with 0 liquidations at a bar low
    above every liquidation price and -1.0 with 10 past it, so the isolated-margin floor binds
    only at or past the liquidation level. The wipe needs a THIRD ingredient -- realized losses
    already booked -- and under isolated margin an account that has lost money cannot still have
    ten full margins posted. The drawdown was honestly valuing a position set the account could
    never have held.

    ``open_positions`` legs are ``(exit_candle, locked_collateral_usd, notional_usd)``; the
    committed margin is the second element, the same one ``process_closed_positions`` returns.

    LAYER (DDD_PATTERNS): infrastructure. ML wrappers hold no business rule, and this is the
    account identity -- arithmetic over the loop's own accumulators, not a risk policy.

    PATTERN (ARCHITECTURE_PATTERNS): none invoked, deliberately. The nearest row is Adapter
    (section 2), and its anti-fit is exactly this case -- "an adapter between two things we
    control is usually two things that should have agreed". ``available_balance`` and
    ``realized_pnl`` are two accumulators in one loop that should have agreed and did not;
    reconciling them with a seam would preserve the disagreement. Naming any pattern for one
    subtraction would be section 9's pattern-as-explanation. What this prevents is concrete: an
    accumulated balance drifts silently from the identity it is meant to equal and nothing
    reports the drift, which is the same failure class as ADR-025's stored verdicts.
    """
    committed = sum(float(leg[1]) for leg in open_positions)
    return float(initial_capital) + float(realized_pnl) - committed


#: Float tolerance the capital check below already applies ("$10,000 / 3 = $3,333.33...").
_CAPITAL_TOLERANCE_USD = 0.01


def entry_scale_for_free_margin(
    *,
    margin_required_usd: float,
    available_balance: float,
    open_position_count: int,
    realistic_mode: bool,
    sizing_follows_capital: bool,
) -> float:
    """Fraction of the planned entry a FLAT account can fund -- 1.0 unless it would otherwise freeze.

    ENGINE-FREEZE-1 (2026-09-24). `free_margin_balance` made the free balance honest, but the
    entry is still sized off ``initial_capital / max_open_positions``. So after ANY net loss an
    account holding no position asks for a margin it can never post again, `should_skip_signal`
    returns "capital" on every remaining signal, and the book reads as a loss when it measured a
    frozen engine. Measured on prod `1d gradient_boosting_clf v2`, perp_3x all-in: 347 signals
    skipped at $7,562.45 free vs $10,000.00 asked, for 11 months after the 2025-10-10 crash.

    A real account with $7,562 places a $7,562 order. Only when NOTHING is open: with positions
    open, a "capital" skip is realistic -- margin is locked and returns on close, so nothing
    freezes. Only when the size was DERIVED from the account (``sizing_follows_capital``): an
    explicit ``position_size`` is a fixed order, and a bot configured to send $1,000 with $500 in
    the account is refused by the exchange every time -- `test_backtester_realistic` pins that.
    Never above 1.0: the upside is not re-sized, so a winning book does not start compounding
    here. A balance at or below the tolerance returns 1.0 and is refused as "capital".
    """
    if not (realistic_mode and sizing_follows_capital) or open_position_count > 0:
        return 1.0
    fits = available_balance >= margin_required_usd - _CAPITAL_TOLERANCE_USD
    if margin_required_usd <= 0.0 or fits or available_balance <= _CAPITAL_TOLERANCE_USD:
        return 1.0
    return float(available_balance) / float(margin_required_usd)


def should_skip_signal(
    signal: int,
    open_positions: list[tuple[int, float, float]],
    available_balance: float,
    *,
    spot_mode: bool,
    max_open_positions: int | None,
    realistic_mode: bool,
    margin_required_usd: float,
    extra_open_slots: int = 0,
    perp_allowed_sides: PerpAllowedSides = PerpAllowedSides.BOTH,
) -> str | None:
    """
    Check if signal should be skipped and return reason string (or None to proceed).

    Skip reasons: 'hold', 'short_spot', 'perp_side_filtered', 'max_pos', 'capital'.

    extra_open_slots: Count positions not represented in open_positions (e.g. compound aggregate).
    perp_allowed_sides: When not spot_mode, restrict which directions may open (perp only; default both).
    """
    if signal == 0:
        return "hold"

    # SPOT exchanges cannot short — you can't sell what you don't own
    if spot_mode and signal == -1:
        return "short_spot"

    if not spot_mode:
        if perp_allowed_sides == PerpAllowedSides.LONG_ONLY and signal == -1:
            return "perp_side_filtered"
        if perp_allowed_sides == PerpAllowedSides.SHORT_ONLY and signal == 1:
            return "perp_side_filtered"

    effective_open = len(open_positions) + extra_open_slots
    if max_open_positions is not None and effective_open >= max_open_positions:
        return "max_pos"

    # Small tolerance (0.01) handles floating-point precision issues
    # Example: $10,000 / 3 = $3,333.33… might cause check to fail
    if realistic_mode and available_balance < margin_required_usd - 0.01:
        return "capital"

    return None
