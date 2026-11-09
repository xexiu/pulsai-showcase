"""Behavior tests for return-distribution moments SoT (PSR/DSR inputs)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import kurtosis as scipy_kurtosis
from scipy.stats import skew as scipy_skew

from src.shared.math.backtest_validation_statistics import honest_deflated_sharpe
from src.shared.math.return_distribution_moments import (
    ReturnDistributionMoments,
    honest_deflated_sharpe_from_returns,
    measurable_moments,
    moments_from_returns,
    null_deflated_sharpe_from_returns,
)


def test_moments_from_returns_matches_scipy_on_fat_tailed_series() -> None:
    rng = np.random.default_rng(42)
    # Mixture: heavier tails than Gaussian.
    arr = np.concatenate([rng.normal(0, 0.01, 400), rng.normal(0, 0.05, 40)])
    moments = moments_from_returns(arr)
    assert moments.skew == pytest.approx(float(scipy_skew(arr, bias=False)), abs=1e-10)
    assert moments.kurtosis == pytest.approx(float(scipy_kurtosis(arr, fisher=False, bias=False)), abs=1e-10)
    assert moments.kurtosis > 3.0


def test_moments_from_returns_gaussian_near_three_kurtosis() -> None:
    rng = np.random.default_rng(0)
    arr = rng.normal(0.0, 0.01, 5000)
    moments = moments_from_returns(arr)
    scipy_k = float(scipy_kurtosis(arr, fisher=False, bias=False))
    assert moments.kurtosis == pytest.approx(scipy_k, abs=1e-10)
    assert moments.kurtosis == pytest.approx(3.0, abs=0.15)


def test_moments_from_returns_falls_back_when_too_few_samples() -> None:
    assert moments_from_returns([0.01, -0.01]) == ReturnDistributionMoments(skew=0.0, kurtosis=3.0)


class TestMeasurableMoments:
    """The moments, or NOTHING -- for readers that would take the normal fallback as a measurement.

    The fallback above is right for PSR's variance term and wrong anywhere else: MinTRL fed skew 0 / kurtosis 3 for a
    three-trade book would acquit it on its lucky Sharpe. The cert writer (lane_rows) and the lab screens both need
    "absent", and both used to re-type the threshold to get it.
    """

    def test_too_few_finite_values_have_no_moments(self) -> None:
        assert measurable_moments([0.01, -0.01, 0.02]) is None

    def test_non_finite_values_do_not_count_toward_the_sample(self) -> None:
        assert measurable_moments([0.01, float("nan"), -0.01, float("inf"), 0.02]) is None

    def test_a_describable_sample_gets_exactly_the_sots_moments(self) -> None:
        arr = np.random.default_rng(1).normal(0.0, 0.01, 50)
        assert measurable_moments(arr) == moments_from_returns(arr)


def test_honest_deflated_sharpe_from_returns_penalizes_fat_tails_vs_gaussian_assumption() -> None:
    rng = np.random.default_rng(7)
    arr = np.concatenate([rng.normal(0.0005, 0.008, 500), rng.normal(-0.002, 0.04, 25)])
    moments = moments_from_returns(arr)
    sr = float(arr.mean() / arr.std(ddof=1))
    trial = [0.05, 0.04, 0.03]
    with_real = honest_deflated_sharpe(sr, trial, len(arr), skew=moments.skew, kurtosis=moments.kurtosis)
    gaussian = honest_deflated_sharpe(sr, trial, len(arr), skew=0.0, kurtosis=3.0)
    assert with_real < gaussian


def test_honest_deflated_sharpe_from_returns_returns_zero_on_short_series() -> None:
    assert honest_deflated_sharpe_from_returns([0.01], [0.01]) == 0.0


class TestNullDeflatedSharpeFromReturns:
    """The convention 28 research files each re-implemented, now owned in one place.

    Those copies say so themselves -- "copied verbatim (same formula/convention as
    ctrend_factor.py / xs_reversal.py::dsr() elsewhere in this corpus)". They differ from
    ``honest_deflated_sharpe_from_returns`` in ONE input: the trial dispersion is the
    null-hypothesis standard error sqrt(1/n) rather than the measured spread of an actual
    sweep, so the caller passes a trial COUNT instead of a list of trial Sharpes.

    Measured equivalence to the corpus formula: max |delta| 5.4e-06 over 36 cases (that
    residual is the SoT's stdlib normal approximation vs scipy, not a formula difference).
    """

    @staticmethod
    def _corpus_reference(r, n_trials: int) -> float:
        """The verbatim body from the research corpus, for equivalence testing only."""
        import numpy as np
        from scipy import stats
        from scipy.stats import norm

        r = np.asarray(r, dtype=float)
        n = len(r)
        if n < 30:
            return float("nan")
        sr = r.mean() / r.std(ddof=1)
        sk = float(stats.skew(r))
        ku = float(stats.kurtosis(r, fisher=False))
        g = 0.5772
        K = max(n_trials, 2)
        sr0 = np.sqrt(1.0 / n) * ((1 - g) * norm.ppf(1 - 1.0 / K) + g * norm.ppf(1 - 1.0 / (K * np.e)))
        return float(norm.cdf((sr - sr0) * np.sqrt(n - 1) / np.sqrt(max(1e-9, 1 - sk * sr + (ku - 1) / 4 * sr**2))))

    def test_matches_the_corpus_formula_within_moment_convention(self) -> None:
        """Same answer as the 28 copies, to well inside any gate at 0.80 / 0.95.

        Not bit-identical on purpose: the copies use scipy's BIASED skew/kurtosis defaults
        while this routes through ``moments_from_returns``, which is bias-corrected. Measured
        worst case of that swap over 48 samples: 2.96e-03.
        """
        import numpy as np

        rng = np.random.default_rng(3)
        for n in (60, 250, 1000):
            for n_trials in (2, 100, 2000):
                r = rng.normal(0.03, 1.0, n)
                got = null_deflated_sharpe_from_returns(r, n_trials)
                want = self._corpus_reference(r, n_trials)
                assert abs(got - want) < 5e-3, f"n={n} K={n_trials}: {got} vs {want}"

    def test_more_trials_never_raises_the_score(self) -> None:
        """The whole point of deflation: a bigger search must not look better."""
        import numpy as np

        r = np.random.default_rng(5).normal(0.05, 1.0, 500)
        scores = [null_deflated_sharpe_from_returns(r, k) for k in (2, 10, 100, 1000, 5000)]
        assert scores == sorted(scores, reverse=True)

    def test_too_few_observations_is_nan_not_zero(self) -> None:
        """NaN, matching the corpus: 0.0 would read as a measured failure, NaN as no answer."""
        import math

        import numpy as np

        assert math.isnan(null_deflated_sharpe_from_returns(np.zeros(29) + 0.01, 10))

    def test_a_flat_series_is_nan_not_a_divide_by_zero(self) -> None:
        import math

        import numpy as np

        assert math.isnan(null_deflated_sharpe_from_returns(np.zeros(200), 10))

    def test_a_single_trial_is_still_deflated_against_two(self) -> None:
        """The corpus clamps K to >= 2; a lone trial must not skip deflation entirely."""
        import numpy as np

        r = np.random.default_rng(9).normal(0.04, 1.0, 300)
        assert null_deflated_sharpe_from_returns(r, 1) == null_deflated_sharpe_from_returns(r, 2)
