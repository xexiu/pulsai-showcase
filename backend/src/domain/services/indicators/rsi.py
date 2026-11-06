"""Relative strength index (RSI) -- ONE home for every RSI the repo computes (owner, 2026-10-19, 8b-RSI).

IMPORTERS/CALLERS: features/feature_momentum (calculate_all's RSI columns) and fast_feature_calculator_prewarm,
features/tv_rule_primitives, targets/target_rsi (the five reversal / hft targets' labels), targets/filtered_target,
infrastructure/ml/chart_json (the chart's RSI pane), catalog.INDICATOR_CALLS, and the lab copies 8b-RSI replaced
(engine/validation/indicators_home_rsi_2026-10-19.txt lists every one).
AFFECTED API: wilder_rsi, wilder_rsi_first_seeded, first_seeded_rsi, cutler_rsi, DEFAULT_RSI_PERIOD, cutler_rsi_of_changes, rsi_from_averages,
price_changes, gains_losses (new); features.numba_momentum.calculate_rsi_numba and
infrastructure.ml.chart_indicators.calculate_rsi moved here. DATA SCHEMAS: none -- float64 arrays in, one per bar out.

One formula, ``100 - 100 / (1 + average gain / average loss)``, over three averages the repo's copies used:
- ``wilder_rsi``: Wilder's RMA seeded at bar ``period`` with the mean of the first ``period`` changes (TA-Lib, Pine
  ``ta.rsi``) -- calculate_all's RSI, the chart's and the targets';
- ``wilder_rsi_first_seeded``: the same RMA started at the first change (pandas ``ewm(alpha=1 / period,
  adjust=False)``; the ema home's recursion, 5e-15 relative to pandas); ``first_seeded_rsi`` takes any alpha (two lab
  copies smooth with an EMA of span n, alpha 2 / (n + 1));
- ``cutler_rsi``: the plain mean of the last ``period`` gains and losses.

Bar 0 has no price change, so its change is NaN -- never 0. Six lab copies prepended ``close[0]`` and so counted a
change of 0 at bar 0: a fabricated flat bar inside the first window (Cutler) or as the seed (first-seeded), which
pulled every early value toward 50. Training reads these values, so the home does not.

``ZeroLoss`` is what RSI reads where the average loss is 0 (a run with no down bar); the copies disagreed, and each
choice moves values the stored models and labels were built on, so it is a parameter, never silently unified:
``hundred`` (RSI 100: TA-Lib, calculate_all, the chart), ``nan`` (no RSI: the pandas copies' ``loss.replace(0,
nan)``), ``rs_hundred`` (RS 100, RSI 99.0099: the five targets' stored labels), ``hundred_or_fifty`` (100 after a
gain, 50 when flat: trading_bots' parity port), ``hundred_or_zero`` (100 after a gain, 0 when flat: TA-Lib's
``100 * gain / (gain + loss)``). The lab's epsilon floors (``loss + 1e-12``, ``max(loss, 1e-12)``) were
``hundred_or_zero`` approximated (``0 / eps`` is 0); they map to it, 1e-9 apart at most (measured).

DISMISSAL-CHECK: not a hypothesis (shared infra).
REUSE-AUDIT: rma.rma_mean_seeded (Wilder's seed and recursion) and ema's first-seeded recursion -- each fused into one
kernel here for speed, bit-equal to composing them (measured),
trailing.trailing_mean (Cutler's window mean) -- imported; the RSI formula and the zero-loss policy are the only new
code. Measured 2026-10-19 on real BTC/USDT 5m (44,180 bars) and 1,000,000 synthetic bars: see the validation record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

import numpy as np

from src.domain.services.indicators.trailing import trailing_mean
from src.shared.utils.numba_jit import jit_inlined, njit_cached

if TYPE_CHECKING:
    import numpy.typing as npt

type ZeroLoss = Literal["hundred", "nan", "rs_hundred", "hundred_or_fifty", "hundred_or_zero"]

#: Wilder's period: the chart's RSI and the lab calls that took the default.
DEFAULT_RSI_PERIOD: Final = 14

_RS_ON_ZERO_LOSS = 100.0  # the targets' labels: RS 100 where the average loss is 0
_RSI_FLAT = 50.0  # hundred_or_fifty: no gain and no loss
#: The fused kernels' policy codes (numba takes no string), one per ZeroLoss literal.
_HUNDRED: Final = 0
_NAN: Final = 1
_RS_HUNDRED: Final = 2
_HUNDRED_OR_FIFTY: Final = 3
_HUNDRED_OR_ZERO: Final = 4
_ZERO_LOSS_CODE: Final = {
    "hundred": _HUNDRED,
    "nan": _NAN,
    "rs_hundred": _RS_HUNDRED,
    "hundred_or_fifty": _HUNDRED_OR_FIFTY,
    "hundred_or_zero": _HUNDRED_OR_ZERO,
}


def price_changes(close: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """``close[t] - close[t - 1]``; bar 0 is NaN (no change is known there)."""
    return np.diff(np.asarray(close, dtype=np.float64), prepend=np.nan)


def gains_losses(changes: npt.ArrayLike) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Each change's gain (its rise, else 0) and loss (its fall as a positive number, else 0); a NaN change stays NaN."""
    values = np.asarray(changes, dtype=np.float64)
    return np.maximum(values, 0.0), np.maximum(-values, 0.0)


def rsi_from_averages(avg_gain: npt.ArrayLike, avg_loss: npt.ArrayLike, zero_loss: ZeroLoss = "hundred") -> npt.NDArray[np.float64]:
    """``100 - 100 / (1 + avg_gain / avg_loss)`` on each bar; where ``avg_loss`` is 0 the ``zero_loss`` policy decides
    (module docstring). A NaN average gives NaN."""
    gain = np.asarray(avg_gain, dtype=np.float64)
    loss = np.asarray(avg_loss, dtype=np.float64)
    flat = loss == 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = gain / loss
        if zero_loss == "rs_hundred":
            rs = np.where(flat, _RS_ON_ZERO_LOSS, rs)
        out = 100.0 - 100.0 / (1.0 + rs)
    if zero_loss == "hundred":
        out[flat] = 100.0
    elif zero_loss == "nan":
        out[flat] = np.nan
    elif zero_loss == "hundred_or_fifty":
        out[flat] = np.where(gain[flat] > 0.0, 100.0, _RSI_FLAT)
    elif zero_loss == "hundred_or_zero":
        out[flat] = np.where(gain[flat] > 0.0, 100.0, 0.0)
    return out


def wilder_rsi(close: npt.ArrayLike, period: int, zero_loss: ZeroLoss = "hundred") -> npt.NDArray[np.float64]:
    """Wilder's RSI (TA-Lib, Pine ``ta.rsi``): the averages are seeded at bar ``period`` with the mean of changes 1 ..
    ``period``, then ``(average * (period - 1) + x) / period``; NaN before bar ``period`` and on a series of
    ``period`` bars or fewer.

    One fused numba pass -- the same arithmetic as rma.rma_mean_seeded over the gains and losses then
    rsi_from_averages (bit-equal, measured), at calculate_all's speed: composed it took 0.60 ms on 44,180 real bars
    and 20.2 ms on 1,000,000, the fused pass 0.28 / 9.3 (2026-10-19)."""
    return _wilder_rsi_bars(np.ascontiguousarray(close, dtype=np.float64), period, _ZERO_LOSS_CODE[zero_loss])


@jit_inlined
def _rsi_at(avg_gain: float, avg_loss: float, code: int) -> float:
    if avg_loss == 0.0:
        if code == _HUNDRED:
            return 100.0
        if code == _NAN:
            return np.nan
        if code == _RS_HUNDRED:
            return 100.0 - 100.0 / (1.0 + _RS_ON_ZERO_LOSS)
        flat = _RSI_FLAT if code == _HUNDRED_OR_FIFTY else 0.0  # else _HUNDRED_OR_ZERO
        return 100.0 if avg_gain > 0.0 else flat
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


@njit_cached
def _first_seeded_rsi_bars(close: npt.NDArray[np.float64], alpha: float, code: int) -> npt.NDArray[np.float64]:
    n = len(close)
    out = np.full(n, np.nan)
    avg_gain = 0.0
    avg_loss = 0.0
    gain_started = False
    loss_started = False
    for i in range(1, n):
        change = close[i] - close[i - 1]
        gain = max(change, 0.0) if not np.isnan(change) else np.nan
        loss = max(-change, 0.0) if not np.isnan(change) else np.nan
        gain_seen = np.isfinite(gain)
        loss_seen = np.isfinite(loss)
        if gain_seen:
            avg_gain = avg_gain + alpha * (gain - avg_gain) if gain_started else gain
            gain_started = True
        if loss_seen:
            avg_loss = avg_loss + alpha * (loss - avg_loss) if loss_started else loss
            loss_started = True
        if gain_seen and loss_seen:
            out[i] = _rsi_at(avg_gain, avg_loss, code)
    return out


@njit_cached
def _wilder_rsi_bars(close: npt.NDArray[np.float64], period: int, code: int) -> npt.NDArray[np.float64]:
    n = len(close)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    avg_gain = 0.0
    avg_loss = 0.0
    for i in range(1, period + 1):  # the seed: changes 1 .. period, summed left to right
        change = close[i] - close[i - 1]
        if change > 0.0:
            avg_gain += change
        else:
            avg_loss += -change
    avg_gain /= period
    avg_loss /= period
    out[period] = _rsi_at(avg_gain, avg_loss, code)
    for i in range(period + 1, n):
        change = close[i] - close[i - 1]
        gain = max(0.0, change)
        loss = 0.0 if change > 0.0 else -change
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi_at(avg_gain, avg_loss, code)
    return out


def first_seeded_rsi(close: npt.ArrayLike, alpha: float, zero_loss: ZeroLoss = "nan") -> npt.NDArray[np.float64]:
    """RSI whose averages are exponential smoothings at ``alpha`` started at the first change (bar 1), no warm-up:
    pandas ``ewm(alpha=alpha, adjust=False)`` of the gains and losses. Wilder's is ``alpha = 1 / period``
    (wilder_rsi_first_seeded); an EMA-smoothed RSI of span n is ``alpha = 2 / (n + 1)``.

    One fused numba pass -- ema.exponential_smoothing of each average (a non-finite value skipped) then
    rsi_from_averages, bit-equal (measured); composed it took 0.51 ms on 44,180 real bars (2026-10-19)."""
    return _first_seeded_rsi_bars(np.ascontiguousarray(close, dtype=np.float64), alpha, _ZERO_LOSS_CODE[zero_loss])


def wilder_rsi_first_seeded(close: npt.ArrayLike, period: int, zero_loss: ZeroLoss = "nan") -> npt.NDArray[np.float64]:
    """Wilder's RSI with the averages started at the first change (bar 1): first_seeded_rsi at ``alpha = 1 / period``."""
    return first_seeded_rsi(close, 1.0 / period, zero_loss)


def cutler_rsi_of_changes(changes: npt.ArrayLike, period: int, zero_loss: ZeroLoss = "nan") -> npt.NDArray[np.float64]:
    """Cutler's RSI of a change series (price changes, or returns): the plain mean of the last ``period`` gains and
    losses; NaN until ``period`` finite changes."""
    means = trailing_mean(np.stack(gains_losses(changes)), period)  # both averages in one numpy call
    return rsi_from_averages(means[0], means[1], zero_loss)


def cutler_rsi(close: npt.ArrayLike, period: int, zero_loss: ZeroLoss = "nan") -> npt.NDArray[np.float64]:
    """Cutler's RSI of a price series: the first value at bar ``period`` (changes 1 .. ``period``)."""
    return cutler_rsi_of_changes(price_changes(close), period, zero_loss)


__all__ = [
    "DEFAULT_RSI_PERIOD",
    "ZeroLoss",
    "cutler_rsi",
    "cutler_rsi_of_changes",
    "first_seeded_rsi",
    "gains_losses",
    "price_changes",
    "rsi_from_averages",
    "wilder_rsi",
    "wilder_rsi_first_seeded",
]
