"""Behavior tests for the standard-normal CDF / inverse-CDF SoT.

Ground truth is scipy (test-only); the production module is stdlib-only.
These guard the shared Φ / Φ⁻¹ relied on by the Deflated-Sharpe gate and the
break-even-AUC cost floor.
"""

from __future__ import annotations

import pytest
from scipy.stats import norm  # test-only ground truth

from src.shared.math.normal_distribution import (
    inverse_standard_normal_cdf,
    standard_normal_cdf,
)


@pytest.mark.parametrize("x", [-3.0, -1.0, -0.25, 0.0, 0.25, 1.0, 2.5])
def test_cdf_matches_scipy(x: float) -> None:
    assert standard_normal_cdf(x) == pytest.approx(float(norm.cdf(x)), abs=1e-12)


def test_cdf_at_zero_is_half() -> None:
    assert standard_normal_cdf(0.0) == pytest.approx(0.5, abs=1e-15)


@pytest.mark.parametrize("p", [0.001, 0.02, 0.1, 0.5, 0.58, 0.9, 0.98, 0.999])
def test_inverse_matches_scipy(p: float) -> None:
    assert inverse_standard_normal_cdf(p) == pytest.approx(float(norm.ppf(p)), abs=1e-7)


@pytest.mark.parametrize("p", [0.01, 0.3, 0.5, 0.73, 0.99])
def test_cdf_inverse_roundtrip(p: float) -> None:
    assert standard_normal_cdf(inverse_standard_normal_cdf(p)) == pytest.approx(p, abs=1e-7)


def test_inverse_is_monotone_increasing() -> None:
    assert inverse_standard_normal_cdf(0.4) < inverse_standard_normal_cdf(0.6)


@pytest.mark.parametrize("p", [-0.1, 0.0, 1.0, 1.5])
def test_inverse_rejects_out_of_range(p: float) -> None:
    with pytest.raises(ValueError, match="probability must be in"):
        inverse_standard_normal_cdf(p)
