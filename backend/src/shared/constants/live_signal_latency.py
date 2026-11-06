"""
SoT: inner ``GenerateSignalUseCase`` wall-clock warn thresholds (ms).

Used when logging ``Signal generation exceeded …`` after feature + inference
on the closed-bar path. Single production bundle vs ensemble uses different
budgets (more work for ensemble vote).

@see src.application.use_cases.generate_signal.GenerateSignalUseCase
"""

from __future__ import annotations

# WARN when inner pipeline (model load + features + predict/ensemble) exceeds this.
LIVE_SIGNAL_INNER_LATENCY_WARN_SINGLE_MODEL_MS: float = 75.0
LIVE_SIGNAL_INNER_LATENCY_WARN_ENSEMBLE_MS: float = 100.0

# How long the renderable-tier half of the signal roster may be reused before it is re-scanned.
#
# MEASURED 2026-08-20 against the real R2 backend: ``tiered_roster_rows()`` costs ~5.0s per call
# and does NOT amortise -- three consecutive calls took 5149ms / 5047ms / 5.1s for the same 9
# rows. It sits on the live-signal beat, so every 5-minute tick paid it, which is what the warm
# path SLA test was failing on (5525ms against a 337.5ms budget).
#
# WHY this is safe to cache at all: the tier inventory changes only when a model is certified,
# shipped or promoted -- an operator-scale event, not a per-tick one. Rescanning it every five
# minutes asked a question whose answer changes maybe weekly.
#
# WHY 15 minutes: comfortably longer than the 5-minute beat so most ticks pay nothing, short
# enough that a newly shipped candidate starts rendering within a quarter of an hour. This is an
# in-process cache, so each worker expires independently and a promotion cannot be pushed;
# the TTL is the whole invalidation story and is deliberately short enough to not need one.
SIGNAL_ROSTER_TIER_CACHE_TTL_SECONDS: float = 900.0


def live_signal_inner_latency_warn_ms(*, n_bundles: int) -> float:
    """Return the inner-pipeline WARN threshold (ms) for ``n_bundles`` production models."""
    if n_bundles > 1:
        return LIVE_SIGNAL_INNER_LATENCY_WARN_ENSEMBLE_MS
    return LIVE_SIGNAL_INNER_LATENCY_WARN_SINGLE_MODEL_MS


def live_signal_latency_other_ms(*, elapsed_ms: float, model_ms: float, feature_ms: float, step_ms: float) -> float:
    """Unattributed remainder, so a logged breakdown accounts for 100% of the total.

    Owner, 2026-09-02, reading a real warning line:

        Signal generation exceeded 75ms: 320.5ms for BTC/USDT 1h
          | breakdown: model=0.1ms, features=51.9ms, predict=0.9ms

    > "0.1+51.9+0.9 isnot 320.3ms... :S"

    Correct: 52.9 of 320.5 ms. The three terms are SAMPLED sub-steps, never a partition — the
    total is measured from `pipeline_start`, while those three cover only the stretches somebody
    thought to wrap in a stopwatch. The remaining 267.6 ms (83%) was the actual problem and the
    line said nothing about it: lazy imports, the calculator lookup, the fired-sources policy
    build, and the chart-marker work that belongs to neither `feature_ms` nor `predict_ms`.

    Deliberately a RESIDUAL, not a fourth stopwatch. A stopwatch measures what its author
    remembered to wrap, which is how this gap opened in the first place; a residual cannot miss
    anything. A large `other` is not noise — it is the instrument saying "the time is somewhere
    nobody has instrumented", which is the most useful thing it could report.

    May be slightly negative (sub-step timers can overlap or round up past the total); that is
    returned as measured rather than clamped, because a negative remainder is itself a real signal
    that the sub-timers double-count, and hiding it would restore the exact class of silent
    mismeasurement this exists to end.
    """
    return elapsed_ms - (model_ms + feature_ms + step_ms)


__all__ = [
    "LIVE_SIGNAL_INNER_LATENCY_WARN_ENSEMBLE_MS",
    "LIVE_SIGNAL_INNER_LATENCY_WARN_SINGLE_MODEL_MS",
    "SIGNAL_ROSTER_TIER_CACHE_TTL_SECONDS",
    "live_signal_inner_latency_warn_ms",
    "live_signal_latency_other_ms",
]
