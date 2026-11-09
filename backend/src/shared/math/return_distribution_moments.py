"""Return-distribution moments for PSR / deflated Sharpe (Bailey & López de Prado).

SoT for skew + Pearson kurtosis passed to ``honest_deflated_sharpe``. Matches
``scipy.stats.skew(..., bias=False)`` and ``scipy.stats.kurtosis(..., fisher=False, bias=False)``
so research harnesses and production gates stay aligned.

Numpy-only (same pattern as ``cross_sectional_ic``); scipy appears in unit tests only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from src.shared.math.backtest_validation_statistics import (
    deflated_sharpe_ratio,
    honest_deflated_sharpe,
)
from src.shared.math.zero_dispersion import is_near_zero_std

#: The unbiased kurtosis below divides by (n - 1)(n - 2)(n - 3); its sample count must clear the largest root.
_KURTOSIS_DENOMINATOR_ROOT = 3
#: The estimator's DOMAIN, not a trade floor: below it skew/kurtosis are undefined -- fall back to Gaussian (kurtosis=3).
_MIN_SAMPLES_FOR_MOMENTS = _KURTOSIS_DENOMINATOR_ROOT + 1

#: The research corpus refuses to score a Sharpe on fewer than 30 observations, and returns
#: NaN rather than 0.0 so "not measurable" cannot be read as "measured and failed".
_CORPUS_MIN_OBSERVATIONS = 30

#: A lone trial still carries selection bias in this convention, so the corpus clamps the
#: trial count to >= 2 rather than letting the deflation benchmark collapse to zero.
_MIN_DEFLATION_TRIALS = 2


@dataclass(frozen=True)
class ReturnDistributionMoments:
    """Skew + full (Pearson) kurtosis for a return sample (normal kurtosis = 3)."""

    skew: float
    kurtosis: float


def moments_from_returns(values: Sequence[float] | np.ndarray) -> ReturnDistributionMoments:
    """Compute sample skew and Pearson kurtosis for PSR/DSR variance adjustment."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n < _MIN_SAMPLES_FOR_MOMENTS:
        return ReturnDistributionMoments(skew=0.0, kurtosis=3.0)

    std = float(arr.std(ddof=1))
    mean = float(arr.mean())
    if is_near_zero_std(std, mean):
        # Trades that all exit at one target carry std ~5e-17, not 0: z-scores of pure noise.
        return ReturnDistributionMoments(skew=0.0, kurtosis=3.0)

    z = (arr - mean) / std
    skew = float(np.sum(z**3) * n / ((n - 1) * (n - 2)))
    kurtosis = float(((n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3))) * np.sum(z**4) - (3.0 * (n - 1) ** 2) / ((n - 2) * (n - 3)) + 3.0)
    return ReturnDistributionMoments(skew=skew, kurtosis=kurtosis)


def measurable_moments(values: Sequence[float] | np.ndarray) -> ReturnDistributionMoments | None:
    """The sample's moments, or None when too few finite values exist to describe a distribution.

    For readers that must not mistake ``moments_from_returns``' normal fallback (skew 0, kurtosis 3) for a
    measurement: fed to MinTRL, that fallback acquits a three-trade book on its lucky Sharpe. The cert's lane rows
    and the lab screens read this instead of re-typing the threshold.
    """
    finite = np.asarray(values, dtype=float)
    if int(np.isfinite(finite).sum()) < _MIN_SAMPLES_FOR_MOMENTS:
        return None
    return moments_from_returns(finite)


def honest_deflated_sharpe_from_returns(
    values: Sequence[float],
    trial_per_period_sharpes: Sequence[float],
    *,
    min_observations: int = 10,
) -> float:
    """Per-period Sharpe + measured moments → ``honest_deflated_sharpe`` (SoT)."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n < min_observations:
        return 0.0
    std = float(arr.std(ddof=1))
    if is_near_zero_std(std, float(arr.mean())):
        return 0.0
    sr = float(arr.mean() / std)
    moments = moments_from_returns(arr)
    return honest_deflated_sharpe(
        sr,
        trial_per_period_sharpes,
        n,
        skew=moments.skew,
        kurtosis=moments.kurtosis,
    )


def null_deflated_sharpe_from_returns(
    values: Sequence[float],
    n_trials: int,
    *,
    min_observations: int = _CORPUS_MIN_OBSERVATIONS,
) -> float:
    """DSR from a return series and a trial COUNT, using the null trial dispersion.

    The sibling ``honest_deflated_sharpe_from_returns`` wants the FULL list of trial Sharpes
    and derives the dispersion from it — the honest form, when the sweep is in hand. This is
    the other convention in Bailey & López de Prado: the dispersion across trials is taken as
    the Sharpe estimator's null standard error, ``sigma = sqrt(1/n)``, so a caller that only
    knows *how many* configs it tried can still deflate.

    THIS EXISTS BECAUSE 28 RESEARCH FILES EACH RE-IMPLEMENTED IT. Their own docstrings admit
    it — "copied verbatim (same formula/convention as ctrend_factor.py / xs_reversal.py::dsr()
    elsewhere in this corpus)". A deflation gate re-typed 28 times is 28 chances to drift on
    the statistic every verdict in the corpus rests on.

    Measured against that corpus body: max |delta| 5.4e-06 over 36 cases from the normal
    approximation alone, and 2.96e-03 worst case from routing skew/kurtosis through
    ``moments_from_returns`` (bias-corrected) instead of scipy's biased defaults. Both are far
    inside the 0.80 / 0.95 gates, and the bias-corrected moments are the better statistic.

    Returns NaN — not 0.0 — when the sample is too short or flat, matching the corpus: a
    missing measurement must not read as a measured failure.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n < min_observations:
        return float("nan")
    std = float(arr.std(ddof=1))
    if is_near_zero_std(std, float(arr.mean())):
        return float("nan")
    moments = moments_from_returns(arr)
    return deflated_sharpe_ratio(
        float(arr.mean() / std),
        n_trials=max(int(n_trials), _MIN_DEFLATION_TRIALS),
        n_observations=n,
        trial_sharpe_std=float(np.sqrt(1.0 / n)),
        skew=moments.skew,
        kurtosis=moments.kurtosis,
    )


__all__ = [
    "ReturnDistributionMoments",
    "honest_deflated_sharpe_from_returns",
    "measurable_moments",
    "moments_from_returns",
    "null_deflated_sharpe_from_returns",
]
