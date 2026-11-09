"""Backtest validation statistics (SoT) — selection-bias-aware strategy gates.

WHY this module exists:
A high backtest Sharpe is trivially achievable after a handful of trials (the
*False Strategy Theorem*). Ranking strategies by raw Sharpe / single-window net
return — as an unguarded config sweep does — selects for luck, not edge. These
pure functions deflate for (a) the number of trials run and (b) backtest
overfitting, and enforce a minimum sample, so a strategy is trusted only when its
edge survives selection bias. They would have rejected the 27-trade,
best-of-~600-trials "winners" produced by the exhaustive target/timeframe sweep.

References:
- Bailey & López de Prado, "The Deflated Sharpe Ratio" (2014).
- Bailey, Borwein, López de Prado & Zhu, "The Probability of Backtest
  Overfitting" — Combinatorially Symmetric Cross-Validation (CSCV).

Stdlib-only by design (this is an import-cost-lean leaf util, like
``backtest_annualization``): the standard-normal Φ / Φ⁻¹ helpers are imported from
``normal_distribution`` (shared SoT — math.erfc CDF + Acklam (2003) inverse, abs
error ≈1e-9). The unit tests verify those against scipy.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import SupportsInt

from src.shared.constants.backtest import (
    BACKTEST_VALIDATION_MIN_TRADES,
    DEFAULT_DEFLATED_SHARPE_CONFIDENCE,
    EXPLORATORY_OOS_MIN_DEFLATED_SHARPE,
    EXPLORATORY_OOS_MIN_TRADES,
    RESEARCH_MIN_TRADES_FLOOR,
    RESEARCH_OOS_BARS_PER_TRADE,
)
from src.shared.constants.timeframes import get_timeframe_delta
from src.shared.math.normal_distribution import inverse_standard_normal_cdf, standard_normal_cdf
from src.shared.math.zero_dispersion import is_near_zero_std

#: Euler-Mascheroni constant - appears in the expected-maximum-of-N-gaussians.
_EULER_MASCHERONI = 0.5772156649015329

#: A dispersion-based statistic (Sharpe / std) needs at least two samples.
_MIN_SAMPLES_FOR_STDEV = 2

#: CSCV needs at least two competing configs and an even, >=2 slice count.
_MIN_PBO_CONFIGS = 2
_MIN_PBO_SLICES = 2
#: Upper bound on slices: CSCV enumerates C(n_slices, n_slices/2) splits, which grows
#: combinatorially (16 -> 12,870; 20 -> 184,756; 24 -> 2.7M). Cap at 20 so an unbounded
#: caller arg can't hang the process. de Prado's canonical S is ~16.
_MAX_PBO_SLICES = 20


def _sharpe_estimator_variance(sharpe: float, skew: float, kurtosis: float) -> float:
    """Variance term of the Sharpe estimator: ``1 - skew*SR + (kurt-1)/4 * SR^2`` (``kurtosis`` non-excess)."""
    return 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe * sharpe


def _sample_std(values: Sequence[float]) -> float:
    """Sample (n-1) standard deviation; 0.0 below two values."""
    n = len(values)
    if n < _MIN_SAMPLES_FOR_STDEV:
        return 0.0
    mean = math.fsum(values) / n
    return math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (n - 1))


def probabilistic_sharpe_ratio(
    observed_sharpe: float,
    benchmark_sharpe: float,
    n_observations: int,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Probability that the true Sharpe exceeds ``benchmark_sharpe`` (PSR).

    PSR = Phi[ (SR - SR*) * sqrt(n-1) / sqrt(1 - skew*SR + (kurt-1)/4 * SR^2) ].

    ``kurtosis`` is the full (non-excess) fourth standardized moment (normal = 3).
    Negative skew and fat tails inflate the Sharpe-estimator variance, lowering
    confidence. Returns 0.0 when there are too few observations to form a
    standard error, or when the moment combination is degenerate.
    """
    if n_observations < _MIN_SAMPLES_FOR_STDEV:
        return 0.0
    variance = _sharpe_estimator_variance(float(observed_sharpe), skew, kurtosis)
    if variance <= 0.0:
        return 0.0
    z = (float(observed_sharpe) - float(benchmark_sharpe)) * math.sqrt(n_observations - 1) / math.sqrt(variance)
    return standard_normal_cdf(z)


def expected_maximum_sharpe(n_trials: int, trial_sharpe_std: float) -> float:
    """Expected maximum Sharpe across ``n_trials`` independent trials (luck floor).

    False Strategy Theorem:
    E[max SR] ~= sigma * [ (1-g)*PhiInv(1 - 1/N) + g*PhiInv(1 - 1/(N*e)) ], g = Euler-Mascheroni.

    This is the Sharpe a backtest would post by chance alone after N trials; it is
    the deflation benchmark. Zero when there is no multiple-testing inflation
    (N ≤ 1) or no dispersion across trials.
    """
    n = int(n_trials)
    std = float(trial_sharpe_std)
    if n <= 1 or std <= 0.0:
        return 0.0
    term1 = (1.0 - _EULER_MASCHERONI) * inverse_standard_normal_cdf(1.0 - 1.0 / n)
    term2 = _EULER_MASCHERONI * inverse_standard_normal_cdf(1.0 - 1.0 / (n * math.e))
    return std * (term1 + term2)


def deflated_sharpe_ratio(
    observed_sharpe: float,
    *,
    n_trials: int,
    n_observations: int,
    trial_sharpe_std: float,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Probability the strategy's true Sharpe beats the N-trial luck floor (DSR).

    DSR = PSR(observed_sharpe, benchmark = expected_maximum_sharpe(N, sigma)). As the
    number of trials grows, the benchmark rises until no observed Sharpe can clear
    it — the formal statement that a best-of-many backtest proves little.
    """
    benchmark = expected_maximum_sharpe(n_trials, trial_sharpe_std)
    return probabilistic_sharpe_ratio(observed_sharpe, benchmark, n_observations, skew=skew, kurtosis=kurtosis)


def honest_deflated_sharpe(
    observed_sharpe: float,
    trial_sharpes: Sequence[float],
    n_observations: int,
    *,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Deflated Sharpe with the two selection-bias inputs DERIVED from the actual sweep.

    ``deflated_sharpe_ratio`` is only honest when ``n_trials`` is the real number of configs
    tried and ``trial_sharpe_std`` is their real dispersion. Passing ``n_trials=1`` (or a tiny
    fixed dispersion) zeroes the deflation and lets a best-of-many backtest masquerade as edge
    — the exact Dev2 gaming vector. This wrapper takes the FULL list of per-config Sharpes the
    sweep produced and derives BOTH inputs from it, so the caller cannot understate the
    multiple-testing burden:

    - ``n_trials`` = ``len(trial_sharpes)`` (you evaluated this many configs);
    - ``trial_sharpe_std`` = the sample std of those Sharpes (measured, not assumed 0.4).

    A single trial carries no selection bias, so the benchmark is 0 and the result reduces to
    the probabilistic Sharpe vs zero — correct, not a loophole. Raises on an empty sweep.
    """
    sharpes = [float(s) for s in trial_sharpes]
    n_trials = len(sharpes)
    if n_trials == 0:
        raise ValueError("trial_sharpes must be non-empty (the configs actually evaluated)")
    trial_sharpe_std = _sample_std(sharpes)
    return deflated_sharpe_ratio(
        observed_sharpe,
        n_trials=n_trials,
        n_observations=n_observations,
        trial_sharpe_std=trial_sharpe_std,
        skew=skew,
        kurtosis=kurtosis,
    )


def _column(rows: Sequence[Sequence[float]], col: int) -> list[float]:
    return [float(r[col]) for r in rows]


def per_period_sharpe(values: Sequence[float]) -> float:
    """Per-period Sharpe (mean / std); 0.0 when dispersion is float-noise.

    SoT for the dispersion-guarded Sharpe used by both CSCV (here) and the
    candidate-set overfitting service. The float-noise decision is the ONE
    scale-relative guard (``zero_dispersion.is_near_zero_std``): an absolute
    1e-6 floor read a real sub-1e-6 spread (funding-scale returns) as no Sharpe.
    """
    n = len(values)
    if n < _MIN_SAMPLES_FOR_STDEV:
        return 0.0
    mean = math.fsum(values) / n
    variance = math.fsum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance)
    if is_near_zero_std(std, mean):
        return 0.0
    return mean / std


def _contiguous_slice_bounds(n_obs: int, n_slices: int) -> list[tuple[int, int]]:
    """Split ``n_obs`` rows into ``n_slices`` contiguous, as-equal-as-possible groups."""
    base, extra = divmod(n_obs, n_slices)
    bounds: list[tuple[int, int]] = []
    start = 0
    for s in range(n_slices):
        size = base + (1 if s < extra else 0)
        bounds.append((start, start + size))
        start += size
    return bounds


def _average_rank(values: Sequence[float], idx: int) -> float:
    """Rank of ``values[idx]`` (1 = worst .. n = best), averaging ties."""
    target = values[idx]
    less = sum(1 for v in values if v < target)
    equal = sum(1 for v in values if v == target)
    return less + (equal + 1) / 2.0


def probability_of_backtest_overfitting(
    returns_matrix: Sequence[Sequence[float]],
    *,
    n_slices: int = 16,
) -> float:
    """Probability of Backtest Overfitting via CSCV (Bailey et al.).

    ``returns_matrix`` is (observations x configs): per-period performance of each
    candidate config. The rows are split into ``n_slices`` contiguous groups; for
    every way to choose half the slices as in-sample (the rest out-of-sample) the
    in-sample-best config's out-of-sample rank is measured. PBO is the fraction of
    splits where the in-sample winner lands at or below the out-of-sample median —
    i.e. where selecting the best in-sample config is no better than a coin flip
    out-of-sample.

    Returns a probability in [0, 1]. Raises ``ValueError`` on a ragged matrix,
    fewer than two configs, an odd / sub-2 / over-cap ``n_slices``, or too few
    observations.

    This is the validated CSCV primitive; its intended consumer is a matrix-producer
    that runs each config across purged time-splits (Arena/optimizer follow-up). The
    leaderboard credibility gate currently uses the cheaper Deflated-Sharpe path.
    """
    rows = [list(map(float, r)) for r in returns_matrix]
    if not rows:
        raise ValueError("returns_matrix must be non-empty")
    n_obs = len(rows)
    n_configs = len(rows[0])
    if any(len(r) != n_configs for r in rows):
        raise ValueError("returns_matrix is ragged: every row needs the same number of configs")
    if n_configs < _MIN_PBO_CONFIGS:
        raise ValueError(f"PBO needs at least {_MIN_PBO_CONFIGS} competing configs")
    if n_slices < _MIN_PBO_SLICES or n_slices % 2 != 0:
        raise ValueError(f"n_slices must be an even integer >= {_MIN_PBO_SLICES}, got {n_slices}")
    if n_slices > _MAX_PBO_SLICES:
        raise ValueError(f"n_slices must be <= {_MAX_PBO_SLICES} (CSCV split count grows combinatorially), got {n_slices}")
    if n_obs < n_slices:
        raise ValueError(f"need at least n_slices ({n_slices}) observations, got {n_obs}")

    bounds = _contiguous_slice_bounds(n_obs, n_slices)
    half = n_slices // 2
    overfit_count = 0
    total = 0
    for is_slices in itertools.combinations(range(n_slices), half):
        is_set = frozenset(is_slices)
        is_rows = [rows[i] for s in is_slices for i in range(*bounds[s])]
        oos_rows = [rows[i] for s in range(n_slices) if s not in is_set for i in range(*bounds[s])]
        is_perf = [per_period_sharpe(_column(is_rows, c)) for c in range(n_configs)]
        oos_perf = [per_period_sharpe(_column(oos_rows, c)) for c in range(n_configs)]
        best_is = max(range(n_configs), key=lambda c: is_perf[c])
        relative_rank = _average_rank(oos_perf, best_is) / (n_configs + 1.0)
        logit = math.log(relative_rank / (1.0 - relative_rank))
        if logit <= 0.0:
            overfit_count += 1
        total += 1
    return overfit_count / total if total else 0.0


@dataclass(frozen=True)
class BacktestValidationVerdict:
    """Outcome of the composite strategy-credibility gate."""

    passed: bool
    num_trades: int
    meets_min_trades: bool
    deflated_sharpe: float
    meets_min_dsr: bool
    reasons: tuple[str, ...]


def evaluate_backtest_validation(
    *,
    num_trades: int,
    observed_sharpe: float,
    n_trials: int,
    trial_sharpe_std: float,
    n_observations: int | None = None,
    min_trades: int = BACKTEST_VALIDATION_MIN_TRADES,
    min_deflated_sharpe: float = DEFAULT_DEFLATED_SHARPE_CONFIDENCE,
) -> BacktestValidationVerdict:
    """Composite gate: a strategy is credible only with enough trades AND a DSR.

    Combines the minimum-trade floor (statistical power) with the Deflated Sharpe
    Ratio (selection-bias survival), Gaussian returns assumed (no caller ever passed skew or
    kurtosis -- measured over every call in apps/api -- so the two knobs are gone and the gate is
    within ruff's eight arguments). ``n_observations`` defaults to ``num_trades`` (per-trade returns). Returns a verdict with per-check booleans and
    human-readable failure reasons.
    """
    n_obs = int(n_observations) if n_observations is not None else int(num_trades)
    dsr = deflated_sharpe_ratio(
        observed_sharpe,
        n_trials=n_trials,
        n_observations=n_obs,
        trial_sharpe_std=trial_sharpe_std,
    )
    meets_min_trades = num_trades >= min_trades
    meets_min_dsr = dsr >= min_deflated_sharpe
    reasons: list[str] = []
    if not meets_min_trades:
        reasons.append(f"insufficient trades: {num_trades} < {min_trades} required for a credible verdict")
    if not meets_min_dsr:
        reasons.append(f"deflated Sharpe {dsr:.3f} < {min_deflated_sharpe:.2f} (edge not robust to {n_trials} trials)")
    return BacktestValidationVerdict(
        passed=meets_min_trades and meets_min_dsr,
        num_trades=int(num_trades),
        meets_min_trades=meets_min_trades,
        deflated_sharpe=dsr,
        meets_min_dsr=meets_min_dsr,
        reasons=tuple(reasons),
    )


def _parse_oos_day(day: str) -> datetime:
    return datetime.strptime(day.strip()[:10], "%Y-%m-%d").replace(tzinfo=UTC)


def estimate_oos_bars(*, timeframe: str, start_date: str, end_date: str) -> int:
    """Approximate OOS bar count from a calendar-day window (for TF-scaled min-trades)."""
    start = _parse_oos_day(start_date)
    end = _parse_oos_day(end_date)
    window_seconds = (end - start).total_seconds()
    if window_seconds <= 0:
        return 0
    bar_seconds = get_timeframe_delta(timeframe).total_seconds()
    return max(1, int(window_seconds / bar_seconds))


def trade_count_from_metrics(metrics: Mapping[str, object]) -> int:
    """Trade count from a backtest-metrics mapping, tolerating ``num_trades`` or ``total_trades``.

    Shared SoT for the credibility gates (Arena leaderboard + model-promotion) so they count
    trades identically. Missing / non-numeric -> 0 (an incomplete backtest fails the trade
    floor, it never silently passes).
    """
    raw = metrics.get("num_trades")
    if raw is None:
        raw = metrics.get("total_trades")
    if not isinstance(raw, SupportsInt | str):
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def resolve_research_min_trades(
    oos_bars: int,
    *,
    floor: int = RESEARCH_MIN_TRADES_FLOOR,
    bars_per_trade: int = RESEARCH_OOS_BARS_PER_TRADE,
    certification_cap: int = BACKTEST_VALIDATION_MIN_TRADES,
) -> int:
    """Scale research min-trades with OOS length: max(floor, bars // bars_per_trade), capped at cert."""
    if oos_bars <= 0:
        return floor
    scaled = oos_bars // bars_per_trade
    return max(floor, min(certification_cap, scaled))


@dataclass(frozen=True)
class OosTieredGateVerdict:
    """Three-tier OOS gate: scout (edge signal) → research (TF-scaled N + DSR) → certification (200 + DSR)."""

    scout_pass: bool
    research_pass: bool
    certification_pass: bool
    oos_bars: int
    min_trades_research: int
    min_trades_certification: int
    net_positive: bool
    pf_above_one: bool
    num_trades: int
    deflated_sharpe: float
    research_validation: BacktestValidationVerdict
    certification_validation: BacktestValidationVerdict

    @property
    def reasons_scout(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.net_positive:
            reasons.append("net return <= 0")
        if not self.pf_above_one:
            reasons.append("profit factor <= 1.0")
        return tuple(reasons)


def evaluate_exploratory_oos_gate(
    *,
    num_trades: int,
    observed_sharpe: float,
    n_trials: int,
    trial_sharpe_std: float,
) -> BacktestValidationVerdict:
    """Exploratory bar: ≥10 trades and honest DSR ≥ 0.80 (research scripts only)."""
    return evaluate_backtest_validation(
        num_trades=num_trades,
        observed_sharpe=observed_sharpe,
        n_trials=n_trials,
        trial_sharpe_std=trial_sharpe_std,
        min_trades=EXPLORATORY_OOS_MIN_TRADES,
        min_deflated_sharpe=EXPLORATORY_OOS_MIN_DEFLATED_SHARPE,
    )


def format_oos_gate_tier(
    verdict: OosTieredGateVerdict,
    *,
    exploratory_pass: bool,
) -> str:
    """Human-readable highest OOS tier for table output (cert > research > exploratory > scout > kill)."""
    if verdict.certification_pass:
        return "cert"
    if verdict.research_pass:
        return "research"
    if exploratory_pass:
        return "exploratory"
    if verdict.scout_pass:
        return "scout"
    return "kill"


__all__ = [
    "BacktestValidationVerdict",
    "OosTieredGateVerdict",
    "deflated_sharpe_ratio",
    "estimate_oos_bars",
    "evaluate_backtest_validation",
    "evaluate_exploratory_oos_gate",
    "expected_maximum_sharpe",
    "format_oos_gate_tier",
    "honest_deflated_sharpe",
    "per_period_sharpe",
    "probabilistic_sharpe_ratio",
    "probability_of_backtest_overfitting",
    "resolve_research_min_trades",
    "trade_count_from_metrics",
]
