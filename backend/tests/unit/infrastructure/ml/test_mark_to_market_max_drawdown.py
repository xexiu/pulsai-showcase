"""The honest mark-to-market drawdown — the number every leverage verdict rests on.

WHY THIS FILE EXISTS. `mark_to_market_max_drawdown` decides `mtm_drawdown_wipe`, which is a KILL
screen: a cell at -100% is reported as an account the user lost, and the book dies. Until
2026-08-12 it had **no direct test coverage at all**, while carrying every leverage kill in the
corpus.

THE DEFECT IT PINS (owner, 2026-08-12: "if sizing, doesn't mean that ALL account is wiped... ONLY
when ALL-IN sizing, correct??"). The original implementation added EVERY open position's own worst
intrabar extreme into the same bar's equity:

    adverse = lows[e0:e1] if direction >= 0 else highs[e0:e1]
    equity[e0:e1] += direction * (adverse - entry_px) / entry_px * size

For a book holding only longs that is right — same instrument, same bar, they all sink together at
the bar LOW. For a book holding longs AND shorts concurrently it marks the longs at the bar LOW and
the shorts at the bar HIGH **in the same bar**. Price cannot be at both ends of its own range at
once, so the resulting drawdown describes a moment that never existed, and it is OVERSTATED.

That is a false-kill generator: a mixed-direction book (any 3-class model with
`max_open_positions > 1`) can be reported as having wiped the account when it did not.

THE CORRECT BOUND. Within a bar, price genuinely reaches the low and genuinely reaches the high —
two real instants. At the low every long is at its worst and every short is simultaneously at its
best; at the high, the reverse. So the worst *achievable* account equity in that bar is

    min(equity_if_price_at_low, equity_if_price_at_high)

which is tight, physically realisable, and collapses to the old answer for single-direction books.
It remains conservative about intrabar PATH (it does not model whether the low or the high came
first) — that is the honest limit of OHLC data and is deliberately left as the safe side.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from src.domain.services.edge_lifecycle.capital_cert_bankruptcy import detect_account_bankruptcy
from src.infrastructure.ml.backtester_drawdown import (
    mark_to_market_max_drawdown,
    mark_to_market_unavailable_reason,
)
from src.infrastructure.ml.backtester_trade_math import merge_planned_exit_with_intrabar_liquidation
from src.shared.constants.backtest_leverage import (
    BACKTEST_EXIT_TYPE_LIQUIDATION,
    BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE,
)
from src.shared.math.linear_isolated_perp import liquidation_price_linear_isolated_long

LONG = 1.0
SHORT = -1.0


@dataclass
class _Trade:
    """Only the attributes the drawdown reads — a full Trade drags in the whole ML stack."""

    entry_candle_index: int
    exit_candle_index: int
    entry_price: float
    direction: float
    size: float
    net_pnl: float


class TestSingleDirectionBooksAreUnchanged:
    """The all-long / all-short cases must keep marking at the bar extreme that actually hurts."""

    def test_a_long_is_marked_at_the_bar_low(self) -> None:
        lows = np.array([100.0, 50.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trade = _Trade(0, 2, 100.0, LONG, 10_000.0, 0.0)

        got = mark_to_market_max_drawdown([trade], lows, highs, 10_000.0)

        # Price halves intrabar: a 100%-of-account long loses 50% of the account at that instant.
        assert got == pytest.approx(-0.5)

    def test_a_short_is_marked_at_the_bar_high(self) -> None:
        lows = np.array([100.0, 100.0, 100.0])
        highs = np.array([100.0, 150.0, 100.0])
        trade = _Trade(0, 2, 100.0, SHORT, 10_000.0, 0.0)

        got = mark_to_market_max_drawdown([trade], lows, highs, 10_000.0)

        assert got == pytest.approx(-0.5)

    def test_two_longs_sink_together_at_the_same_low(self) -> None:
        """Same instrument, same bar, same low — genuinely simultaneous, so they DO stack."""
        lows = np.array([100.0, 80.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trades = [
            _Trade(0, 2, 100.0, LONG, 5_000.0, 0.0),
            _Trade(0, 2, 100.0, LONG, 5_000.0, 0.0),
        ]

        got = mark_to_market_max_drawdown(trades, lows, highs, 10_000.0)

        # -20% on 10,000 of combined exposure = -2,000 on a 10,000 account.
        assert got == pytest.approx(-0.2)


class TestMixedDirectionBooksAreNotOverstated:
    """THE FALSE-KILL FIX: a hedged book must not be marked at both ends of one bar."""

    def test_a_perfectly_hedged_book_has_no_drawdown(self) -> None:
        """Equal long and short on the same instrument is flat — the account cannot move.

        The stacking implementation reported this as a LOSS on both legs at once: the long marked
        at the bar low AND the short marked at the bar high, which is two different prices in one
        instant. A perfectly hedged book losing money is the reductio that proves it wrong.
        """
        lows = np.array([100.0, 60.0, 100.0])
        highs = np.array([100.0, 140.0, 100.0])
        trades = [
            _Trade(0, 2, 100.0, LONG, 10_000.0, 0.0),
            _Trade(0, 2, 100.0, SHORT, 10_000.0, 0.0),
        ]

        got = mark_to_market_max_drawdown(trades, lows, highs, 10_000.0)

        assert got == pytest.approx(0.0)

    def test_a_hedged_book_is_never_reported_as_wiped(self) -> None:
        """The false KILL, stated as money: this book cannot lose, and must not read as ruin."""
        lows = np.array([100.0, 1.0, 100.0])
        highs = np.array([100.0, 500.0, 100.0])
        trades = [
            _Trade(0, 2, 100.0, LONG, 10_000.0, 0.0),
            _Trade(0, 2, 100.0, SHORT, 10_000.0, 0.0),
        ]

        got = mark_to_market_max_drawdown(trades, lows, highs, 10_000.0)

        assert got is not None
        assert got > -1.0, "a fully hedged book reported as a -100% wipe is a false kill"
        assert got == pytest.approx(0.0)

    def test_net_exposure_drives_the_drawdown_not_the_gross(self) -> None:
        """Long 10k + short 4k = net long 6k, so the LOW is the bar's worst reachable instant."""
        lows = np.array([100.0, 50.0, 100.0])
        highs = np.array([100.0, 120.0, 100.0])
        trades = [
            _Trade(0, 2, 100.0, LONG, 10_000.0, 0.0),
            _Trade(0, 2, 100.0, SHORT, 4_000.0, 0.0),
        ]

        got = mark_to_market_max_drawdown(trades, lows, highs, 10_000.0)

        # At the low (-50%): long -5,000, short +2,000 -> -3,000 on a 10,000 account.
        # At the high (+20%): long +2,000, short -800 -> +1,200. The low is the worst.
        assert got == pytest.approx(-0.3)


class TestRuinIsStillDetected:
    """Removing the overstatement must NOT let a genuine wipe through."""

    def test_an_all_in_leveraged_long_that_blows_up_still_reads_minus_one(self) -> None:
        """All-in at 5x: a 20% adverse move wipes the account. This MUST stay a kill."""
        lows = np.array([100.0, 79.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trade = _Trade(0, 2, 100.0, LONG, 50_000.0, -10_000.0)

        got = mark_to_market_max_drawdown([trade], lows, highs, 10_000.0)

        assert got == pytest.approx(-1.0)

    def test_equity_is_floored_at_zero_not_negative(self) -> None:
        """A real account stops at zero — the drawdown floor is -100%, never worse."""
        lows = np.array([100.0, 10.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trade = _Trade(0, 2, 100.0, LONG, 80_000.0, -10_000.0)

        got = mark_to_market_max_drawdown([trade], lows, highs, 10_000.0)

        assert got == pytest.approx(-1.0)


class TestItSaysWhyTheHonestDrawdownIsUnavailable:
    """The fallback to bar_close was silent, and silence is why a published row stayed understated.

    MEASURED 2026-09-13 on BTC/USDT 1d, leverage 5, 2025-01-01..2026-07-28: prod AND localhost both
    stamped `bar_close` with 90 trades and byte-identical numbers. Identical across environments
    proves the cause is shared code, and at that point there was no way to narrow it further from
    outside the process, because nothing recorded WHICH precondition had failed.

    Each case below is one of the five, so the reason string can never silently stop discriminating.
    """

    LOWS = np.array([100.0, 90.0, 100.0])
    HIGHS = np.array([100.0, 110.0, 100.0])

    def _ok(self) -> _Trade:
        return _Trade(0, 2, 100.0, LONG, 1_000.0, 0.0)

    def test_no_trades_says_so(self) -> None:
        assert mark_to_market_unavailable_reason([], self.LOWS, self.HIGHS) == "no trades"

    def test_a_missing_price_series_is_named(self) -> None:
        reason = mark_to_market_unavailable_reason([self._ok()], None, self.HIGHS)

        assert reason is not None
        assert "low" in reason

    def test_both_missing_series_are_named_together(self) -> None:
        """Reporting one at a time is how a two-part defect takes two round trips to find."""
        reason = mark_to_market_unavailable_reason([self._ok()], None, None)

        assert reason is not None
        assert "low" in reason
        assert "high" in reason

    def test_a_length_mismatch_reports_both_lengths(self) -> None:
        reason = mark_to_market_unavailable_reason([self._ok()], self.LOWS, self.HIGHS[:-1])

        assert reason is not None
        assert "mismatch" in reason
        assert "3" in reason
        assert "2" in reason

    def test_a_trade_without_candle_indices_is_identified_by_position(self) -> None:
        bad = self._ok()
        bad.exit_candle_index = None  # type: ignore[assignment]

        reason = mark_to_market_unavailable_reason([self._ok(), bad], self.LOWS, self.HIGHS)

        assert reason is not None
        assert "trade 1" in reason

    def test_a_computable_case_returns_no_reason_so_it_cannot_cry_wolf(self) -> None:
        """Guard the guard: a reason on a working input would make every honest run look broken."""
        trades = [self._ok()]

        assert mark_to_market_unavailable_reason(trades, self.LOWS, self.HIGHS) is None
        assert mark_to_market_max_drawdown(trades, self.LOWS, self.HIGHS, 10_000.0) is not None


class TestRefusesToGuess:
    def test_missing_price_series_returns_none(self) -> None:
        """None lets the caller fall back to closed-trade DD rather than invent a number."""
        trade = _Trade(0, 1, 100.0, LONG, 100.0, 0.0)

        assert mark_to_market_max_drawdown([trade], None, None, 10_000.0) is None

    def test_no_trades_returns_none(self) -> None:
        assert mark_to_market_max_drawdown([], np.array([1.0]), np.array([1.0]), 10_000.0) is None

    def test_incomplete_candle_indexing_returns_none(self) -> None:
        trade = _Trade(0, 1, 100.0, LONG, 100.0, 0.0)
        trade.exit_candle_index = None  # type: ignore[assignment]

        assert mark_to_market_max_drawdown([trade], np.array([1.0, 1.0]), np.array([1.0, 1.0]), 10_000.0) is None

    def test_mismatched_series_lengths_return_none(self) -> None:
        trade = _Trade(0, 1, 100.0, LONG, 100.0, 0.0)

        got = mark_to_market_max_drawdown([trade], np.array([100.0, 100.0]), np.array([100.0]), 10_000.0)

        assert got is None


class TestPositionLossIsCappedAtItsOwnMargin:
    """Under ISOLATED margin a position cannot lose more than its margin — the mark ignores that.

    MEASURED 2026-08-17 over the whole cert corpus (90 artifacts, 888,999 cells):

        DD <= wipe threshold        36,781  (4.1%)   -> screened out as RUIN
          ... with ZERO liquidations 3,174           -> "wiped" while nothing liquidated
          ... AND profitable           504           -> impossible pair, money suppressed

    This function values each open position linearly from entry with NO lower bound. The trade loop
    instead closes a position at `liquidation_price_linear_isolated_long/short`
    (BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE = 0.004 — a -19.60% move for a 5x long), so a position
    the loop would have closed keeps accruing loss here.

    `mtm_drawdown_wipe` is in RUIN_REASONS, so an overstated drawdown is a FALSE KILL — the mirror
    of the 2026-07-25 closed-trade defect: too DEEP rather than too shallow.

    WHY ONE POSITION CANNOT SHOW IT: a position sized to the whole account floors at -100% either
    way, because equity is clamped at 0. The gap opens only when concurrent positions risk LESS than
    the account — the normal fractional-sizing case, i.e. every cell the cert recommends.

    RED ON PURPOSE. The correction must reuse the existing liquidation-price helper as its single
    definition of how far a position can fall, and that needs a signature change rather than a
    one-line clamp: this function receives NOTIONAL `size` and neither margin nor leverage, so it
    cannot locate the liquidation price at all. That is wider than the discovery and moves 36,781
    cells across 90 artifacts, so it is not shipped in the same breath as finding it.
    """

    def test_the_cap_binds_once_leverage_is_supplied(self) -> None:
        """GREEN half: 3 longs, $5,000 notional each at 5x = $1,000 margin each, $10,000 account.

        Uncapped the book marks 3 x -$2,500 = -$7,500 (-75%). Each position is liquidated once its
        own $1,000 margin is gone, so the deepest the account can honestly go is 3 x -$1,000 =
        -$3,000, i.e. -30%. The other $7,000 was never at risk in those trades.

        NOTE (C-0x, 2026-09-15): the FULL-MARGIN floor asserted here is deliberate and was
        re-confirmed after being challenged. The engine's own loop closes a position 0.4% of
        notional earlier, at `liquidation_price_linear_isolated_long`, so -$980 is what it books;
        but at a live venue the liquidation fee consumes the maintenance buffer and the trader
        loses the WHOLE margin, which is what this number models. Flooring at the loop's price
        instead makes every leveraged drawdown in the corpus shallower -- the direction the
        2026-07-25 honest-engine correction exists to prevent.
        """
        lows = np.array([100.0, 50.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trades = [_Trade(0, 2, 100.0, LONG, 5_000.0, 0.0) for _ in range(3)]

        got = mark_to_market_max_drawdown(trades, lows, highs, 10_000.0, leverage=5.0)

        assert got == pytest.approx(-0.30)

    def test_omitting_leverage_preserves_the_old_uncapped_number_exactly(self) -> None:
        """Backward compatibility is the whole reason `leverage` defaults to None.

        Every existing caller and every artifact on disk must be untouched until a caller opts in
        by passing its lane's multiple. Changing 36,781 cells silently would be far worse than the
        overstatement being fixed.
        """
        lows = np.array([100.0, 50.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trades = [_Trade(0, 2, 100.0, LONG, 5_000.0, 0.0) for _ in range(3)]

        assert mark_to_market_max_drawdown(trades, lows, highs, 10_000.0) == pytest.approx(-0.75)

    def test_a_spot_book_is_unaffected_by_the_cap(self) -> None:
        """leverage=1 means margin == notional, so the floor can never bind before the equity floor."""
        lows = np.array([100.0, 50.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trade = _Trade(0, 2, 100.0, LONG, 10_000.0, 0.0)

        assert mark_to_market_max_drawdown([trade], lows, highs, 10_000.0, leverage=1.0) == pytest.approx(-0.5)

    @pytest.mark.xfail(
        reason="mark is uncapped and lacks the margin/leverage needed to reach the liquidation price",
        strict=True,
    )
    def test_three_fractional_longs_cannot_lose_more_than_their_combined_margin(self) -> None:
        """3 longs, $5,000 notional each = 5x on $1,000 margin, in a $10,000 account, bar -50%.

        Uncapped the book marks 3 x -$2,500 = -$7,500, an account drawdown of -75%. Each position is
        liquidated once its own $1,000 margin is gone, so the deepest the account can honestly go is
        3 x -$1,000 = -$3,000, i.e. -30%. The other $7,000 was never at risk in those trades.
        """
        lows = np.array([100.0, 50.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trades = [_Trade(0, 2, 100.0, LONG, 5_000.0, 0.0) for _ in range(3)]

        got = mark_to_market_max_drawdown(trades, lows, highs, 10_000.0)

        assert got == pytest.approx(-0.30), (
            "each isolated position is liquidated at its own margin, so three 5x positions on "
            "$1,000 of margin each can cost the account at most $3,000"
        )


class TestTheImpossiblePairCannotBeProducedAgain:
    """`DD-CONTRADICTS-FINAL`: a -100% drawdown beside a final ABOVE initial, not bankrupt.

    Three rows in the pre-commitment corpus carry it — `1d v2` (PROD, $26,244 with 9 liquidations),
    `1d v12` ($13,404) and `1d v42` ($12,815, ZERO liquidations). A -100% mark means the account
    touched zero, which cannot coexist with ending in profit; `drawdown_contradicts_capital` exists
    to detect the pair, and those rows are old-engine output.

    THE CAUSE WAS THE UNCAPPED MARK. Valuing each open position from entry with no lower bound let
    concurrent leveraged positions stack losses the isolated-margin loop would never have taken, so
    a profitable book could still print -100%. With the cap wired (`2668fed73`) the floor is the sum
    of the positions' own margins, which is BELOW the account except when a position is sized to the
    whole account — and that case floors at -100% honestly, because it genuinely is ruin.

    The cap also gets SHALLOWER as leverage RISES, which reads backwards until you hold notional
    fixed: at 8x the same $5,000 position needs only $625 of margin, so three of them can cost
    $1,875 of a $10,000 account, not $7,500.
    """

    def test_profitable_leveraged_positions_never_report_a_wipe(self) -> None:
        lows = np.array([100.0, 50.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trades = [_Trade(0, 2, 100.0, LONG, 5_000.0, +900.0) for _ in range(3)]

        for leverage, expected in ((3.0, -0.5), (5.0, -0.3), (8.0, -0.1875)):
            got = mark_to_market_max_drawdown(trades, lows, highs, 10_000.0, leverage=leverage)

            assert got is not None
            assert got == pytest.approx(expected), f"{leverage}x"
            assert got > -1.0, "a profitable book reported as a -100% wipe is the impossible pair"

    def test_the_old_uncapped_path_is_what_produced_the_contradiction(self) -> None:
        """Not a regression guard — evidence for WHY those three rows exist."""
        lows = np.array([100.0, 50.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trades = [_Trade(0, 2, 100.0, LONG, 5_000.0, +900.0) for _ in range(3)]

        assert mark_to_market_max_drawdown(trades, lows, highs, 10_000.0) == pytest.approx(-0.75)

    def test_genuine_ruin_still_floors_at_minus_one_even_capped(self) -> None:
        """The cap must not become an excuse: an all-in position IS its own margin, so it can ruin.

        UNCHANGED by the C-0x liquidation-price floor, and the reason is worth recording because I
        first predicted it WOULD change and was wrong. The intrabar mark at bar 1 does move
        (-$10,500 uncapped, floored to -$9,800, leaving $200). It is not what produces the -1.0:
        the trade CLOSES at bar 2 with a realized -$10,000, `realized[2:]` steps to exactly zero,
        and the equity path reaches zero there through the closed book rather than through the
        mark. Honest ruin is detected by realized PnL first; the mark is the second detector, for
        intrabar wipes the closed book cannot see.
        """
        lows = np.array([100.0, 79.0, 100.0])
        highs = np.array([100.0, 100.0, 100.0])
        trade = _Trade(0, 2, 100.0, LONG, 50_000.0, -10_000.0)

        got = mark_to_market_max_drawdown([trade], lows, highs, 10_000.0, leverage=5.0)

        assert got == pytest.approx(-1.0)
        assert detect_account_bankruptcy(initial_capital=10_000.0, trades=[trade], final_balance=0.0).account_bankrupt, (
            "the realized-PnL walk calls this account ruined on its own"
        )


class TestTheFloorIsTheMarginWhereTheExchangeUsesTheLiquidationPrice:
    """C-0x -- why `1d lightgbm v42` finishes +30% with ZERO liquidations and is stamped $0.

    The class above fixed the UNCAPPED mark and asserted the cap now binds. It only ever
    exercised books whose posted margins sum to LESS than the account (3 positions on a $10,000
    account), and its own note says so: the floor "is BELOW the account except when a position is
    sized to the whole account". At `10pct` sizing that assumption stops holding -- ten positions
    x $1,000 of margin IS the whole account -- so the residual defect becomes visible at exactly
    the sizing the cert recommends.

    WHAT IS MEASURED AND NOT IN DOUBT. At `10pct` sizing the ten posted margins sum to exactly the
    $10,000 account, so when the floor binds on all ten the mark lands on precisely -100.0%.
    `_is_full_wipe` reads that `-1.0`, `detect_account_bankruptcy` stamps `account_bankrupt`, and
    `apply_bankruptcy_to_capital_lane_row` rewrites `final_capital` to $0. A book whose realized
    year-end is +30% is reported to the user as a lost account. Both tests below prove that path.

    WHAT I FIRST BLAMED, AND WHY IT WAS WRONG -- recorded because the wrong fix was written, run
    and reverted, and the reasoning is the useful part. The cap floors a position at its FULL
    MARGIN while the loop (`merge_planned_exit_with_intrabar_liquidation`) closes it 0.4% of
    notional earlier at `liquidation_price_linear_isolated_long`, booking $968 rather than $1,000
    on an $8,000 notional at 8x. Ten positions x $32 = $320, exactly the gap between a survived
    -96.8% and an exact -100.0%, so re-flooring at the loop's price looked like the fix.

    It is not. At a live venue the liquidation fee consumes the maintenance buffer and the trader
    loses the WHOLE margin, which is what the full-margin floor models and what
    `TestARuinedAccountSaysSo::test_an_intrabar_wipe_is_disclosed_even_though_every_closed_trade_is_green`
    asserts ("a 12.5% adverse move at 8x consumes the entire margin"). Re-flooring made that test
    fail and made every leveraged drawdown in the corpus SHALLOWER -- the precise direction the
    2026-07-25 honest-engine correction exists to prevent. The floor is conservative-correct.

    C-0-LOOP ANSWERED 2026-09-16, and the answer is NOT in this function. Driving the mark and
    `merge_planned_exit_with_intrabar_liquidation` on one ten-position perp_8x book shows the two
    instruments AGREE wherever they can be compared: at a bar low above every liquidation price
    the mark reads -0.96 with 0 liquidations, and past every liquidation price it reads -1.0 with
    10. The floor binds only at or past the liquidation level, so the mark alone cannot
    manufacture a wipe -- which is what `test_the_floor_binds_only_at_or_past_the_liquidation_price`
    below now pins.

    The wipe needs a THIRD ingredient the earlier reading missed: realized losses already booked.
    Ten longs only 10% underwater -- comfortably above the 12.10% that liquidates at 8x, so the
    loop is RIGHT to report zero -- plus -$2,000 of realized loss takes the account mark to
    exactly zero. Under isolated margin that state is impossible: an account down $2,000 cannot
    still have ten $1,000 margins posted. The engine built it anyway, because
    `process_closed_positions` returned each closed leg's FULL original margin and realized PnL
    never reached `available_balance` at all. Measured: 3 of 54 entries funded from $1,000 while
    the account held $718 / $434 / $153. Fixed by `backtester_capital.free_margin_balance`, which
    derives the free balance from the account identity once per bar; on that same fixture the
    drawdown moved -1.0 -> -0.8968 and the final balance $0.00 -> $1,037.75, with liquidations
    still 0. The regression test is
    `tests/unit/infrastructure/ml/test_backtester_margin_absorbs_realized_pnl.py`.

    So the drawdown was never the liar. It honestly valued a position set the account could not
    have held, and the defect was in the collateral accounting that produced it. The two tests
    that stood `xfail(strict)` on the opposite belief are replaced below by the measurement.

    No trade in this book is a liquidation: `_Trade` models only what the drawdown reads, and the
    drawdown never sees an exit type.
    """

    INITIAL = 10_000.0
    LEVERAGE = 8.0
    MAX_OPEN = 10  # "10pct" sizing
    MARGIN = INITIAL / MAX_OPEN  # $1,000 posted per position
    NOTIONAL = MARGIN * LEVERAGE  # $8,000 of exposure per position
    ENTRY = 100_000.0

    def _liquidation_price(self) -> float:
        return liquidation_price_linear_isolated_long(self.ENTRY, int(self.LEVERAGE), BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE)

    def _book(self) -> list[_Trade]:
        """Ten concurrent longs, every one closing GREEN -- the realized book ends +30%."""
        per_trade_profit = (self.INITIAL * 0.30) / self.MAX_OPEN
        return [_Trade(0, 5, self.ENTRY, LONG, self.NOTIONAL, per_trade_profit) for _ in range(self.MAX_OPEN)]

    def _bars_through_the_floor(self) -> tuple[np.ndarray, np.ndarray]:
        """A bar whose low is below every position's full-margin price, so the floor binds."""
        lows = np.full(6, self.ENTRY, dtype=float)
        highs = np.full(6, self.ENTRY, dtype=float)
        lows[3] = self.ENTRY * (1.0 - 1.0 / self.LEVERAGE) - 5_000.0
        return lows, highs

    def test_the_maintenance_buffer_is_the_venues_fee_not_the_traders_money(self) -> None:
        """The per-position gap, in dollars, between the liquidation TRIGGER and the full-margin floor.

        The venue takes the position over at the trigger and closes it against the bankruptcy price; the buffer
        between them is its liquidation fee / insurance fund, so the trader loses the whole margin -- what the floor
        models and, since LIQ-ONE (2026-10-18), what the loop books too (test_backtester_trade_math)."""
        move_to_the_trigger = self.NOTIONAL * (self.ENTRY - self._liquidation_price()) / self.ENTRY

        assert move_to_the_trigger < self.MARGIN
        assert self.MARGIN - move_to_the_trigger == pytest.approx(BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE * self.NOTIONAL)
        assert self.MARGIN - move_to_the_trigger == pytest.approx(32.0)

    def test_the_floor_binds_only_at_or_past_the_liquidation_price(self) -> None:
        """C-0-LOOP's answer: the mark and the loop never actually disagree.

        Reaching the full-margin floor means moving 1/L against the entry; the venue closes at
        `1/L - mmr`, which is EARLIER. So a floored position has always passed its liquidation
        price, and the loop scanning the same bar lows must see it. Measured both sides of that
        threshold on one ten-position perp_8x book:

            low above every liq price   dd -0.96   liquidation_exits 0
            low past every liq price    dd -1.0    liquidation_exits 10

        The mark alone therefore cannot produce `-1.0` beside `liquidation_exits 0`. Whatever
        does, it is not this function -- see the class docstring.
        """
        liq_px = self._liquidation_price()
        margin_floor_px = self.ENTRY * (1.0 - 1.0 / self.LEVERAGE)

        assert margin_floor_px < liq_px, "the floor must sit BELOW the venue's close, or the loop could miss it"

        for move, expect_liquidation in ((0.120, False), (0.130, True)):
            lows = np.full(6, self.ENTRY, dtype=float)
            highs = np.full(6, self.ENTRY, dtype=float)
            lows[3] = self.ENTRY * (1.0 - move)
            trades = [_Trade(0, 5, self.ENTRY, LONG, self.NOTIONAL, 0.0) for _ in range(self.MAX_OPEN)]

            dd = mark_to_market_max_drawdown(trades, lows, highs, self.INITIAL, leverage=self.LEVERAGE)
            liquidated = [
                merge_planned_exit_with_intrabar_liquidation(
                    [0],
                    [self.ENTRY],
                    int(LONG),
                    int(self.LEVERAGE),
                    BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE,
                    (5, self.ENTRY, "time"),
                    lows,
                    highs,
                )[2]
                == BACKTEST_EXIT_TYPE_LIQUIDATION
                for _ in trades
            ]

            assert dd is not None
            assert all(liquidated) is expect_liquidation, f"loop disagrees with the {move:.1%} move"
            assert (dd == pytest.approx(-1.0)) is expect_liquidation, f"mark disagrees with the {move:.1%} move: {dd}"

    def test_the_same_book_crosses_the_wipe_threshold_by_leverage_alone(self) -> None:
        """MEASURED on v42's real ladder: the drawdown is ~LINEAR in leverage, so the wipe is
        arithmetic rather than an outcome.

        One artifact, one confirm window, the frozen tuple `tpsl_7_5 / 10pct / hold 24`, ONLY the
        leverage varying -- the same 101 trades and ZERO liquidations in every row:

            perp_3x  $11,134.52  -47.7%      perp_6x  $12,269.04  -84.5%
            perp_4x  $11,512.70  -61.0%      perp_7x  $12,647.22  -95.0%
            perp_5x  $11,890.87  -73.2%      perp_8x       $0.00 -100.0%

            (B&H over the same window: $7,145.51 -- five of the six BEAT it)

        Five liquidation-clean lanes beat buy-and-hold; the sixth reads $0 and is stamped bankrupt.
        Nothing liquidated at ANY rung, so the $0 is not a different outcome -- it is the identical
        book with the per-position floor summing past the account.

        This reproduces that SHAPE rather than those dollars: the positions, the window and the
        trade book are held fixed and only `leverage` moves, so any monotone deepening is produced
        by the mark alone. The point is not that deepening is wrong -- more leverage IS more risk --
        but that the point at which it trips `_is_full_wipe` is set by arithmetic, while
        `liquidation_exits` stays 0 throughout. Two instruments, one cell, no agreement.
        """
        # `10pct` sizing fixes the MARGIN at initial/10; the NOTIONAL is margin x leverage.
        # My first attempt fixed the NOTIONAL instead and the ladder came out INVERTED, because
        # the floor is notional/leverage -- a fixed notional means a BIGGER margin at LOWER
        # leverage. The cert varies the notional, which is why its drawdowns deepen with leverage.
        move = 0.126  # just past 1/8, so the floor binds at 8x and at no lower rung
        lows = np.full(6, self.ENTRY, dtype=float)
        highs = np.full(6, self.ENTRY, dtype=float)
        lows[3] = self.ENTRY * (1.0 - move)

        by_lane: dict[float, float | None] = {}
        for leverage in (3.0, 4.0, 5.0, 6.0, 7.0, 8.0):
            notional = self.MARGIN * leverage
            trades = [_Trade(0, 5, self.ENTRY, LONG, notional, 0.0) for _ in range(self.MAX_OPEN)]
            by_lane[leverage] = mark_to_market_max_drawdown(trades, lows, highs, self.INITIAL, leverage=leverage)

        depths = [dd for dd in (by_lane[lev] for lev in sorted(by_lane)) if dd is not None]
        assert len(depths) == len(by_lane), f"a lane measured no drawdown: {by_lane}"
        assert depths == sorted(depths, reverse=True), f"not monotone in leverage: {by_lane}"
        assert depths[0] > -1.0, "the lowest rung is not a wipe"
        assert depths[-1] == pytest.approx(-1.0), "the highest rung trips the wipe threshold"

    def test_the_wipe_needs_a_position_set_the_account_could_not_have_funded(self) -> None:
        """Where the v42 `$0` actually came from, and it is upstream of this function.

        Ten longs only 10% underwater -- the venue closes at 12.10%, so NOTHING liquidates and
        the loop is right to report zero -- reach -100% as soon as the account has already
        realized -$2,000. The mark is honest about that book; the book is the impossible part,
        because an account down $2,000 cannot still have ten $1,000 margins posted.

        This pins the arithmetic so the cause cannot be re-litigated. The FIX lives in
        `backtester_capital.free_margin_balance`, and its regression test is
        `test_backtester_margin_absorbs_realized_pnl.py`.
        """
        lows = np.full(6, self.ENTRY, dtype=float)
        highs = np.full(6, self.ENTRY, dtype=float)
        lows[3] = self.ENTRY * (1.0 - 0.100)  # above every liquidation price at 8x

        by_realized: dict[float, float | None] = {}
        for realized in (0.0, -1_000.0, -2_000.0):
            # One closed loser books its loss before the low; ten stay open across it.
            closed = _Trade(0, 1, self.ENTRY, LONG, self.NOTIONAL, realized)
            book = [closed, *(_Trade(2, 5, self.ENTRY, LONG, self.NOTIONAL, 0.0) for _ in range(self.MAX_OPEN))]
            by_realized[realized] = mark_to_market_max_drawdown(book, lows, highs, self.INITIAL, leverage=self.LEVERAGE)

        assert by_realized[0.0] == pytest.approx(-0.8), "no realized loss: the ten marks alone stop at -80%"
        assert by_realized[-1_000.0] == pytest.approx(-0.9)
        assert by_realized[-2_000.0] == pytest.approx(-1.0), "the wipe arrives with the realized loss, not with a liquidation"

        wiped = detect_account_bankruptcy(
            initial_capital=self.INITIAL,
            trades=[_Trade(0, 1, self.ENTRY, LONG, self.NOTIONAL, -2_000.0)],
            final_balance=self.INITIAL - 2_000.0,
            mark_to_market_drawdown=by_realized[-2_000.0],
        )
        assert wiped.account_bankrupt, "that -1.0 is what apply_bankruptcy_to_capital_lane_row rewrites to $0"


def _reference_realized(trades: list[_Trade], n: int, initial: float) -> np.ndarray:
    """The pre-PERF-MTM-NUMBA realized curve, kept verbatim as the regression reference: O(bars x trades)."""
    realized = np.full(n, initial)
    for t in trades:
        realized[min(max(t.exit_candle_index, 0), n - 1) :] += t.net_pnl
    return realized


class TestTheRealizedCurveIsBuiltInOnePass:
    """PERF-MTM-NUMBA (2026-10-02): the realized PnL step was `realized[x:] += pnl` per trade -- O(bars x trades),
    24 % of a 5m cell (300k bars x 5,000 trades). One cumulative sum gives the same curve in O(bars + trades)."""

    @pytest.mark.parametrize("leverage", [None, 5.0])
    def test_drawdown_equals_the_per_trade_reference_on_a_random_mixed_book(self, leverage: float | None) -> None:
        rng = np.random.default_rng(3)
        n = 4_000
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
        lows, highs = close * (1 - np.abs(rng.normal(0, 0.003, n))), close * (1 + np.abs(rng.normal(0, 0.003, n)))
        trades = []
        for ei in np.sort(rng.integers(0, n - 50, 300)):
            xi = int(ei + rng.integers(1, 48))
            d = float(rng.choice([LONG, SHORT]))
            trades.append(_Trade(int(ei), xi, float(close[ei]), d, 2_000.0, d * 2_000.0 * (close[xi] / close[ei] - 1)))
        got = mark_to_market_max_drawdown(trades, lows, highs, 10_000.0, leverage=leverage)
        # The reference DD, built from the verbatim old realized curve plus the unchanged open-position marks.
        realized = _reference_realized(trades, n, 10_000.0)
        at_low, at_high = realized.copy(), realized.copy()
        for t in trades:
            unit = t.direction * t.size / t.entry_price
            lo, hi = (
                unit * (lows[t.entry_candle_index : t.exit_candle_index] - t.entry_price),
                unit * (highs[t.entry_candle_index : t.exit_candle_index] - t.entry_price),
            )
            if leverage is not None:
                lo, hi = np.maximum(lo, -t.size / leverage), np.maximum(hi, -t.size / leverage)
            at_low[t.entry_candle_index : t.exit_candle_index] += lo
            at_high[t.entry_candle_index : t.exit_candle_index] += hi
        eq = np.maximum(np.minimum(at_low, at_high), 0.0)
        peak = np.maximum.accumulate(eq)
        want = max(float(np.min(np.where(peak > 0, (eq - peak) / peak, 0.0))), -1.0)
        assert got == pytest.approx(want, abs=1e-12)
