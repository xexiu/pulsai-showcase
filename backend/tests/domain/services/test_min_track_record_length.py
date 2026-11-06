"""How many observations does a Sharpe need? The literature answers it; 100 was a guess.

`MIN_TRADES_FOR_SHARPE = 100` was calibrated from one anecdote, and its own comment says so: the
2026-08-03 triage put `8h/xgboost/v137` on top with SR 4.48 from 30 trades returning +0.01 total,
so someone picked 100. A real observation producing an arbitrary threshold.

The rigorous answer is **Minimum Track Record Length** — Bailey & López de Prado (2012), "The
Sharpe Ratio Efficient Frontier" — the SAME paper family as the Deflated Sharpe Ratio this repo
already computes in `honest_deflated_sharpe`. Using DSR while guessing at the sample-size
requirement is using half of one framework.

    MinTRL = 1 + [1 - γ₃·SR + (γ₄-1)/4·SR²] · (Z_α / (SR - SR*))²

        SR   observed Sharpe (same periodicity as the observations)
        SR*  benchmark Sharpe to beat (0 = "better than nothing")
        γ₃   skew of returns
        γ₄   kurtosis of returns (3 = normal)
        Z_α  normal critical value (1.645 at 95%)

WHY THIS ANSWERS THE TIMEFRAME QUESTION. MinTRL is not timeframe-indexed — it depends on the
RETURN DISTRIBUTION. A book with SR 2.5 and benign moments needs far fewer observations than one
with SR 0.3. Higher timeframes are not held to a different statistical bar; they simply accumulate
observations more slowly, so the same requirement takes longer in calendar time. That is the
honest version of "a 5m model is not the same as a 12h model".

NEGATIVE SKEW AND FAT TAILS RAISE THE BAR, which is exactly right for crypto: a book that wins
small and often while occasionally losing catastrophically needs MORE evidence, not less.
"""

from __future__ import annotations

import pytest

from src.domain.services.min_track_record_length import min_track_record_length


class TestAgainstTheFormula:
    def test_it_matches_the_published_formula_term_by_term(self) -> None:
        """γ₃=0, γ₄=3, SR=1 -> bracket = 1 - 0 + (3-1)/4 = 1.5, so MinTRL = 1 + 1.5*(Z/1)^2.

        NOT `1 + (Z/SR)^2`. That shortcut only holds when the bracket happens to equal 1, and
        asserting it was my error rather than the formula's.
        """
        bracket = 1.0 - 0.0 * 1.0 + (3.0 - 1.0) / 4.0 * 1.0**2

        got = min_track_record_length(sharpe=1.0, skew=0.0, kurtosis=3.0)

        assert got == pytest.approx(1 + bracket * (1.645 / 1.0) ** 2, rel=1e-9)
        assert got == pytest.approx(5.059, abs=1e-3)

    def test_a_stronger_sharpe_needs_fewer_observations(self) -> None:
        strong = min_track_record_length(sharpe=2.5, skew=0.0, kurtosis=3.0)
        weak = min_track_record_length(sharpe=0.5, skew=0.0, kurtosis=3.0)

        assert strong is not None
        assert weak is not None
        assert strong < weak

    def test_negative_skew_raises_the_requirement(self) -> None:
        """Win-small-often / lose-big books need MORE evidence. Crypto's signature shape."""
        symmetric = min_track_record_length(sharpe=1.0, skew=0.0, kurtosis=3.0)
        left_tailed = min_track_record_length(sharpe=1.0, skew=-1.5, kurtosis=3.0)

        assert symmetric is not None
        assert left_tailed is not None
        assert left_tailed > symmetric

    def test_fat_tails_raise_the_requirement(self) -> None:
        normal = min_track_record_length(sharpe=1.0, skew=0.0, kurtosis=3.0)
        fat = min_track_record_length(sharpe=1.0, skew=0.0, kurtosis=9.0)

        assert normal is not None
        assert fat is not None
        assert fat > normal


class TestRefusesToAnswerWhenItCannot:
    def test_a_sharpe_at_or_below_the_benchmark_is_unanswerable(self) -> None:
        """No sample size proves a book beats a bar it does not clear. None, never a number."""
        assert min_track_record_length(sharpe=0.0, skew=0.0, kurtosis=3.0) is None
        assert min_track_record_length(sharpe=-0.4, skew=0.0, kurtosis=3.0) is None
        assert min_track_record_length(sharpe=0.9, skew=0.0, kurtosis=3.0, benchmark_sharpe=1.0) is None

    def test_missing_moments_yield_none(self) -> None:
        assert min_track_record_length(sharpe=None, skew=0.0, kurtosis=3.0) is None
        assert min_track_record_length(sharpe=1.0, skew=None, kurtosis=3.0) is None
        assert min_track_record_length(sharpe=1.0, skew=0.0, kurtosis=None) is None

    def test_a_nonsense_kurtosis_yields_none(self) -> None:
        """Kurtosis < 1 makes the bracket term negative — a distribution that cannot exist."""
        assert min_track_record_length(sharpe=1.0, skew=0.0, kurtosis=0.0) is None


class TestAgainstTheCorpus:
    def test_v42_confirm_clears_the_literature_bar_even_at_a_weak_sharpe(self) -> None:
        """v42's pre-committed confirm: SR 0.263 over 100 trades -> MinTRL ~= 41.5.

        I expected this to FAIL and it passes, which is worth pinning. The flat 100-trade floor
        and MinTRL agree on v42 by coincidence, not by construction.

        v42 was killed by its -100% MTM drawdown, NOT by sample size. Two independent screens that
        must never be conflated: "not enough evidence" and "the evidence shows ruin" are different
        verdicts with different fixes.
        """
        need = min_track_record_length(sharpe=0.263, skew=0.0, kurtosis=3.0)

        assert need is not None
        assert need == pytest.approx(41.5, abs=0.5)
        assert need < 100

    def test_a_strong_book_clears_on_far_fewer_than_100(self) -> None:
        """The flat floor also FAILS in the other direction: it blocks strong short books.

        v41's cert cell: SR 0.496 over 71 trades. A book at SR 2.0 would need ~2 observations by
        the closed form, yet the flat 100 would reject it -- the floor is not conservative, it is
        simply unrelated to the question.
        """
        need = min_track_record_length(sharpe=2.0, skew=0.0, kurtosis=3.0)

        assert need is not None
        assert need < 100
