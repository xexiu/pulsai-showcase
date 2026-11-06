"""Minimum Track Record Length — how many observations a Sharpe actually needs.

Bailey & López de Prado (2012), "The Sharpe Ratio Efficient Frontier", *Journal of Risk* 15(2).
Same paper family as the Deflated Sharpe Ratio this repo already computes in
`honest_deflated_sharpe`; using DSR while GUESSING the sample-size requirement is using half of
one framework.

    MinTRL = 1 + [1 - γ₃·SR + (γ₄-1)/4·SR²] · (Z_α / (SR - SR*))²

        SR   observed Sharpe, same periodicity as the observations counted
        SR*  benchmark Sharpe to beat (0 = "better than not trading")
        γ₃   skew of the return series
        γ₄   kurtosis (3 = normal, NOT excess kurtosis)
        Z_α  normal critical value (1.645 at 95% one-sided)

WHAT IT REPLACES. `MIN_TRADES_FOR_SHARPE = 100` was calibrated from a single anecdote and its own
comment says so: the 2026-08-03 triage put `8h/xgboost/v137` on top with SR 4.48 from 30 trades
returning +0.01 total, so someone picked 100. A real observation producing an arbitrary number.

A flat floor is wrong in BOTH directions, which is the tell that it is not measuring the right
thing:

  * too LENIENT for weak books — v42's confirm at SR 0.263 over exactly 100 trades cleared the
    floor while proving nothing;
  * too STRICT for strong ones — a book at SR 2.0 needs ~2 observations by the closed form, yet
    the floor rejects it at 99 trades.

ON THE TIMEFRAME QUESTION (owner, 2026-08-12: "5m is not the same as 12h... or inventing 100 magic
number?"). Correct, and MinTRL answers it properly: the requirement is NOT timeframe-indexed, it
is DISTRIBUTION-derived. A 12h book is not held to a different statistical bar; it simply
accumulates observations 24x slower than a 30m one, so the same requirement takes far longer in
calendar time. Indexing the floor by timeframe would have been a second guess on top of the first.

NEGATIVE SKEW AND FAT TAILS RAISE THE REQUIREMENT, which is exactly right for crypto: a book that
wins small and often while occasionally losing catastrophically needs MORE evidence, not less.

RETURNS None WHEN THE QUESTION IS UNANSWERABLE. If the observed Sharpe does not exceed the
benchmark, no sample size proves it does — the honest answer is "no length suffices", never a
number.
"""

from __future__ import annotations

from typing import Final

#: One-sided 95% normal critical value. 95% is the convention in the source paper.
Z_95: Final = 1.645


def min_track_record_length(
    *,
    sharpe: float | None,
    skew: float | None,
    kurtosis: float | None,
    benchmark_sharpe: float = 0.0,
    z: float = Z_95,
) -> float | None:
    """Observations needed for `sharpe` to beat `benchmark_sharpe` at the `z` confidence level.

    `kurtosis` is RAW (3 = normal), not excess — passing excess kurtosis understates the
    requirement, which is the direction that admits bad books.

    None when unanswerable: a missing moment, a Sharpe at or below the benchmark (no length
    proves it), or a kurtosis below 1 (the bracket term goes negative, describing a distribution
    that cannot exist).
    """
    if sharpe is None or skew is None or kurtosis is None:
        return None

    excess = float(sharpe) - float(benchmark_sharpe)
    if excess <= 0.0:
        return None  # no track record length proves a book beats a bar it does not clear

    if float(kurtosis) < 1.0:
        return None

    sr = float(sharpe)
    variance_term = 1.0 - float(skew) * sr + (float(kurtosis) - 1.0) / 4.0 * sr * sr
    if variance_term <= 0.0:
        return None

    return 1.0 + variance_term * (float(z) / excess) ** 2


def has_sufficient_track_record(
    *,
    observations: int | None,
    sharpe: float | None,
    skew: float | None,
    kurtosis: float | None,
    benchmark_sharpe: float = 0.0,
) -> bool | None:
    """True when `observations` meets MinTRL. None when MinTRL cannot be computed.

    None is deliberately NOT False: "we cannot tell" and "provably too short" are different
    findings, and collapsing them is how an unmeasured book gets recorded as a failed one.
    """
    need = min_track_record_length(sharpe=sharpe, skew=skew, kurtosis=kurtosis, benchmark_sharpe=benchmark_sharpe)
    if need is None or observations is None:
        return None
    return float(observations) >= need
