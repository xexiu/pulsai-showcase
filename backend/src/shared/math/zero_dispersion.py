"""The ONE answer to "is this standard deviation (or variance) float noise from a constant series?".

IMPORTERS/CALLERS: every product guard that divides by a sample dispersion -- Sharpe / Sortino / IC /
ICIR / z-scores, correlation pre-checks, drift baselines. AFFECTED API: none. DATA SCHEMAS: none.

RELATIVE, because the noise is. A constant float64 series of value x has a computed std of up to
~6e-16 * |x| (np.std, np.var, pandas, the math.fsum two-pass; n up to 1e5), so a constant 1.2e9
column reads 4.8e-7 while a real one-tick move on a 1e-8-priced coin is 2.2e-13: no ABSOLUTE
threshold sits between them. ``max(|mean|, 1)`` keeps a unit floor for ratio-minus-one data
(returns), whose noise is ~eps whatever the return's size. ``NEAR_ZERO_STD_THRESHOLD`` then sits
>= 100x above the measured noise and >= 100x below the smallest real dispersion; the measurement is
a test, rerun it to re-derive the value: tests/unit/shared/math/test_zero_dispersion.py.

NaN is degenerate: nothing can be divided by it.

Out of reach of ANY threshold, measured: online and cumsum-difference rolling estimators carry
noise set by the history they ran over (6e-9 .. 8e-7 relative), above a real one-tick window.
Those sites need a stable algorithm, not a different epsilon.
"""

from __future__ import annotations

from typing import Any, overload

import numpy as np
from numpy.typing import NDArray

from src.shared.constants import NEAR_ZERO_STD_THRESHOLD

type _Scalar = float | np.floating[Any]
type _Values = _Scalar | NDArray[np.floating[Any]]


@overload
def is_near_zero_std(std: _Scalar, mean: _Scalar) -> bool: ...
@overload
def is_near_zero_std(std: NDArray[np.floating[Any]], mean: _Values) -> NDArray[np.bool_]: ...
def is_near_zero_std(std: _Values, mean: _Values) -> bool | NDArray[np.bool_]:
    """True when ``std`` of a series centred on ``mean`` is float noise (or NaN): do not divide by it."""
    return _not_above(std, _noise_floor(mean))


@overload
def is_near_zero_variance(variance: _Scalar, mean: _Scalar) -> bool: ...
@overload
def is_near_zero_variance(variance: NDArray[np.floating[Any]], mean: _Values) -> NDArray[np.bool_]: ...
def is_near_zero_variance(variance: _Values, mean: _Values) -> bool | NDArray[np.bool_]:
    """The variance form of :func:`is_near_zero_std` (same floor, squared)."""
    floor = _noise_floor(mean)
    return _not_above(variance, floor * floor)


def _noise_floor(mean: _Values) -> Any:
    return NEAR_ZERO_STD_THRESHOLD * np.maximum(np.abs(mean), 1.0)


def _not_above(value: _Values, floor: Any) -> bool | NDArray[np.bool_]:
    degenerate = np.logical_not(np.greater(value, floor))
    return bool(degenerate) if np.ndim(degenerate) == 0 else degenerate
