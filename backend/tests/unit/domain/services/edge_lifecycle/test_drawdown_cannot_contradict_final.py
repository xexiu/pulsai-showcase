"""A −100% drawdown cannot coexist with an account that finished ABOVE its start.

MEASURED 2026-08-16 across the 13 pre-commitment confirms: 3 rows record `max_drawdown: -1.0`
(−100%) while their own `final_capital` is ABOVE `initial_capital`, `account_bankrupt` is False and
`fantasy_post_ruin_trades` is 0. `1d_42_lightgbm` is the sharpest: −100% drawdown, **$12,815 from
$10,000**, zero liquidations.

Those cannot both be true. An account marked to zero is dead — it cannot finish up 28%, and the
engine flags `fantasy_post_ruin_trades` precisely to catch a book that "recovers" after ruin. It
flagged none.

WHICH number is wrong was ASSUMED here and the assumption was backwards. This line read "So the
drawdown is the wrong number, not the capital" until C-0 replayed the cell on 2026-09-15
(`POST /admin/research-loop/select-confirm`, bounded to the stored end). That replay first seemed to
settle it the other way -- `max_drawdown -1.0` again beside `account_bankrupt True` and `$0.00` --
and was then corrected the same evening by reading the cell's realized book: v42 ends **+$3,025
(+30%)**, never lost more than $581 on a trade, took 0 liquidations, and its own `by_year` drawdown is
-86.5%. The `$0.00` is the bankruptcy stamp zeroing that book because the headline reads -1.0. Only
prod v2's wipe is confirmed real. So neither number is trusted by default: the predicate only ever
claimed the PAIR is impossible, and which half is wrong is a per-cell measurement (C-0x).

WHY IT MATTERS BEYOND TIDINESS. This exact figure has now caused a wrong verdict in BOTH directions
inside one corpus: `v42` was KILLED on it once (retracted as unverifiable), and I published it as a
1.79× passer, then retracted it as ruin, then restored it — three readings of one impossible pair.
A number that can be read either way is worse than a missing one, because each reader picks.

That mixed-direction overstatement is REAL and is a second, separate cause of the same pair: before
2026-08-12 a fractional multi-position book marked every position at its OWN worst intrabar extreme,
so longs were marked at the bar LOW while shorts sat at the bar HIGH, and a hedged book could
measure −100% having lost nothing. It is fixed and pinned by `TestMixedDirectionBooksAreNotOverstated`.
It is simply not what happened to `1d_42`, which is a single-direction 10%-sized book that really
did die. The engine-side regression for THAT path lives in
`tests/infrastructure/ml/test_backtester_metrics.py::TestARuinedAccountSaysSo`.

REUSE-AUDIT: lives beside `is_thin_sample` / `headline_survivors` in `capital_cert_headline` — the
module that already decides which cells are publishable. Considered a standalone validator module
(rejected: a second home for "is this cell trustworthy" is how filters drift apart, which this
session already paid for with the thin-headline DSR).
"""

from __future__ import annotations

from src.domain.services.edge_lifecycle.capital_cert_headline import drawdown_contradicts_capital


class TestTheImpossiblePair:
    def test_a_total_drawdown_with_a_profit_is_impossible(self) -> None:
        """v42's actual cell: −100% drawdown, $12,815 from $10,000, liq 0, not bankrupt."""
        assert drawdown_contradicts_capital(
            {
                "max_drawdown": -1.0,
                "final_capital": 12_815.45,
                "initial_capital": 10_000.0,
                "account_bankrupt": False,
                "fantasy_post_ruin_trades": 0,
            }
        )

    def test_a_total_drawdown_with_a_dead_account_is_consistent(self) -> None:
        """Real ruin: the account IS at zero, so −100% is the truth, not a contradiction."""
        assert not drawdown_contradicts_capital({"max_drawdown": -1.0, "final_capital": 0.0, "initial_capital": 10_000.0, "account_bankrupt": True})

    def test_a_total_drawdown_that_ended_bankrupt_is_consistent(self) -> None:
        assert not drawdown_contradicts_capital({"max_drawdown": -1.0, "final_capital": 120.0, "initial_capital": 10_000.0, "account_bankrupt": True})

    def test_post_ruin_trades_mean_the_wipe_was_real(self) -> None:
        """The engine flags fantasy trades exactly when a book kept trading after ruin."""
        assert not drawdown_contradicts_capital(
            {
                "max_drawdown": -1.0,
                "final_capital": 12_000.0,
                "initial_capital": 10_000.0,
                "account_bankrupt": False,
                "fantasy_post_ruin_trades": 7,
            }
        )


class TestOrdinaryCellsAreUntouched:
    def test_a_survivable_drawdown_is_never_flagged(self) -> None:
        assert not drawdown_contradicts_capital({"max_drawdown": -0.447, "final_capital": 17_131.0, "initial_capital": 10_000.0})

    def test_a_losing_book_with_a_deep_drawdown_is_fine(self) -> None:
        assert not drawdown_contradicts_capital({"max_drawdown": -0.837, "final_capital": 7_021.0, "initial_capital": 10_000.0})

    def test_a_missing_drawdown_is_not_a_contradiction(self) -> None:
        """Absent is a different defect from impossible; this predicate answers only the latter."""
        assert not drawdown_contradicts_capital({"final_capital": 12_000.0, "initial_capital": 10_000.0})

    def test_a_missing_capital_cannot_contradict_anything(self) -> None:
        assert not drawdown_contradicts_capital({"max_drawdown": -1.0})

    def test_an_empty_cell_is_not_a_contradiction(self) -> None:
        assert not drawdown_contradicts_capital({})
