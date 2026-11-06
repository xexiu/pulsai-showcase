"""Standard-normal CDF / inverse-CDF (SoT) — stdlib-only, import-cost-lean.

WHY this module exists:
The standard-normal Φ and Φ⁻¹ are needed by more than one validation primitive
(Deflated/Probabilistic Sharpe in ``backtest_validation_statistics`` and the
break-even-AUC cost floor in ``cost_floor``). Duplicating the closed-form CDF and
the Acklam inverse-CDF across modules invites silent drift, so they live here once.

Stdlib-only by design (no scipy / numpy): the CDF uses ``math.erfc`` (exact) and
the inverse-CDF uses Acklam's (2003) rational approximation (abs error ≈ 1e-9).
The unit tests verify both against scipy as ground truth.
"""

from __future__ import annotations

import math

# Acklam (2003) inverse-normal-CDF rational approximation coefficients.
_ACKLAM_A = (
    -3.969683028665376e01,
    2.209460984245205e02,
    -2.759285104469687e02,
    1.383577518672690e02,
    -3.066479806614716e01,
    2.506628277459239e00,
)
_ACKLAM_B = (
    -5.447609879822406e01,
    1.615858368580409e02,
    -1.556989798598866e02,
    6.680131188771972e01,
    -1.328068155288572e01,
)
_ACKLAM_C = (
    -7.784894002430293e-03,
    -3.223964580411365e-01,
    -2.400758277161838e00,
    -2.549732539343734e00,
    4.374664141464968e00,
    2.938163982698783e00,
)
_ACKLAM_D = (
    7.784695709041462e-03,
    3.224671290700398e-01,
    2.445134137142996e00,
    3.754408661907416e00,
)
_ACKLAM_P_LOW = 0.02425
_ACKLAM_P_HIGH = 1.0 - _ACKLAM_P_LOW


def standard_normal_cdf(x: float) -> float:
    """Φ(x) via the complementary error function (exact)."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def inverse_standard_normal_cdf(p: float) -> float:
    """Φ⁻¹(p) via Acklam's rational approximation (abs error ≈ 1e-9)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"probability must be in (0, 1), got {p}")
    if p < _ACKLAM_P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((_ACKLAM_C[0] * q + _ACKLAM_C[1]) * q + _ACKLAM_C[2]) * q + _ACKLAM_C[3]) * q + _ACKLAM_C[4]) * q + _ACKLAM_C[5]) / (
            (((_ACKLAM_D[0] * q + _ACKLAM_D[1]) * q + _ACKLAM_D[2]) * q + _ACKLAM_D[3]) * q + 1.0
        )
    if p <= _ACKLAM_P_HIGH:
        q = p - 0.5
        r = q * q
        return (
            (((((_ACKLAM_A[0] * r + _ACKLAM_A[1]) * r + _ACKLAM_A[2]) * r + _ACKLAM_A[3]) * r + _ACKLAM_A[4]) * r + _ACKLAM_A[5])
            * q
            / (((((_ACKLAM_B[0] * r + _ACKLAM_B[1]) * r + _ACKLAM_B[2]) * r + _ACKLAM_B[3]) * r + _ACKLAM_B[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((_ACKLAM_C[0] * q + _ACKLAM_C[1]) * q + _ACKLAM_C[2]) * q + _ACKLAM_C[3]) * q + _ACKLAM_C[4]) * q + _ACKLAM_C[5]) / (
        (((_ACKLAM_D[0] * q + _ACKLAM_D[1]) * q + _ACKLAM_D[2]) * q + _ACKLAM_D[3]) * q + 1.0
    )


__all__ = [
    "inverse_standard_normal_cdf",
    "standard_normal_cdf",
]
