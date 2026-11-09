"""Exit-strategy grid — the SoT set of exit overlays swept by the honest backtest.

``ExitProfile`` + the ``build_*`` families live here (in ``src``) so BOTH production
(training Step 8's honest exit sweep) AND the research harnesses can import ONE grid
definition. Field names match ``BacktestRequest`` (percent SL/TP: ``2.0`` == 2%).

Previously these lived in ``src/research/research_execution_grid.py``; that module now
re-exports from here so existing research call sites keep working with a single ``ExitProfile``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Required, TypedDict

from src.domain.services.exit_label_codec import encode_tpsl_label
from src.shared.constants.backtest_leverage import max_sl_pct_for_leverage

#: Barrier-style exits hold at most this many bars before timing out (``None`` => TF default).
_BARRIER_HOLD = 24

# Honest 81-cell sweep bounds (8x8 SL/TP at 1% steps) — the canonical FIFO OOS grid.
_FIFO_SL_MIN = 1.0
_FIFO_SL_MAX = 8.0
_FIFO_TP_MIN = 1.0
_FIFO_TP_MAX = 8.0
_FIFO_STEP = 1.0


class ExitHubFields(TypedDict, total=False):
    """The ``BacktestRequest`` exit fields one overlay sets; a key it leaves out takes the engine default
    (``cert.model_spec.EXIT_PARAM_DEFAULTS``). The ``thin_*`` keys are the thin-stop ladder's levers."""

    exit_strategy: Required[str]
    stop_loss_pct: float
    take_profit_pct: float
    risk_reward_ratio: float
    atr_period: int
    atr_multiplier: float
    max_sl_pct: float
    trail_pct: float
    trail_activation_pct: float
    min_net_pct: float
    thin_be_r: float
    thin_tp_r: tuple[float, ...]
    thin_runner_parts: int
    thin_use_trail: bool


@dataclass(frozen=True)
class ExitProfile:
    """One exit overlay: a label + the ``BacktestRequest`` fields that define it."""

    label: str
    hub_fields: ExitHubFields
    holding_periods: int | None = None  # None => use the signal timeframe's default


def build_fixed_tpsl_exits(
    *,
    sl_min: float = 2.0,
    sl_max: float = 4.0,
    tp_min: float = 1.0,
    tp_max: float = 6.0,
    step: float = 1.0,
) -> tuple[ExitProfile, ...]:
    """Full SL x TP grid (defaults: SL 2-4%, TP 1-6%, step 1%).

    ``step`` is configurable so callers can trade granularity for compute (a finer 0.5% step
    multiplies the cell count, which raises the multiple-testing / deflation burden).
    """
    out: list[ExitProfile] = []
    sl = sl_min
    while sl <= sl_max + 1e-9:
        tp = tp_min
        while tp <= tp_max + 1e-9:
            sl_i, tp_i = round(sl, 2), round(tp, 2)
            out.append(
                ExitProfile(
                    # STOP-LOSS FIRST — the `tpsl` prefix reads take-profit-then-stop-loss and
                    # encodes the reverse. Reading it the other way turned v41's +18.0% into
                    # -6.0% and produced a false "the cert engine is untrustworthy" alarm
                    # (2026-08-12). Built through the codec so the order lives in one place.
                    label=encode_tpsl_label(stop_loss_pct=sl_i, take_profit_pct=tp_i),
                    hub_fields={
                        "exit_strategy": "fixed_tpsl",
                        "stop_loss_pct": sl_i,
                        "take_profit_pct": tp_i,
                    },
                    holding_periods=_BARRIER_HOLD,
                )
            )
            tp += step
        sl += step
    return tuple(out)


def build_risk_reward_exits(
    *,
    sl_min: float = 2.0,
    sl_max: float = 4.0,
    rr_values: tuple[float, ...] = (1.5, 2.0, 3.0),
) -> tuple[ExitProfile, ...]:
    """Risk-reward exits: a few SL anchors x reward multiples (TP derived from SL x RR)."""
    return tuple(
        ExitProfile(
            label=f"rr_{round(sl, 2):g}_{rr:g}",
            hub_fields={
                "exit_strategy": "risk_reward",
                "stop_loss_pct": round(sl, 2),
                "risk_reward_ratio": rr,
            },
            holding_periods=_BARRIER_HOLD,
        )
        for sl in (sl_min, sl_min + 1.0, sl_max)
        for rr in rr_values
    )


def build_alt_exit_families(*, include_extended_rr: bool = True) -> tuple[ExitProfile, ...]:
    """Non-fixed-tpsl strategies already supported by the backtester (hold / atr / trailing / ...)."""
    rr = (
        build_risk_reward_exits()
        if include_extended_rr
        else (
            ExitProfile(
                label="rr_2_2",
                hub_fields={
                    "exit_strategy": "risk_reward",
                    "stop_loss_pct": 2.0,
                    "risk_reward_ratio": 2.0,
                },
                holding_periods=_BARRIER_HOLD,
            ),
        )
    )
    return (
        ExitProfile(
            label="hold",
            hub_fields={"exit_strategy": "fixed_holding"},
            holding_periods=None,
        ),
        *rr,
        ExitProfile(
            label="atr_x2",
            hub_fields={"exit_strategy": "atr_based", "atr_period": 14, "atr_multiplier": 2.0},
            holding_periods=_BARRIER_HOLD,
        ),
        ExitProfile(
            label="atr_x3",
            hub_fields={"exit_strategy": "atr_based", "atr_period": 14, "atr_multiplier": 3.0},
            holding_periods=_BARRIER_HOLD,
        ),
        ExitProfile(
            label="dyn_tpsl_x2",
            hub_fields={"exit_strategy": "dynamic_tpsl", "atr_period": 14, "atr_multiplier": 2.0},
            holding_periods=_BARRIER_HOLD,
        ),
        ExitProfile(
            label="dyn_tpsl_x3",
            hub_fields={"exit_strategy": "dynamic_tpsl", "atr_period": 14, "atr_multiplier": 3.0},
            holding_periods=_BARRIER_HOLD,
        ),
        ExitProfile(
            label="trail_1_1",
            hub_fields={
                "exit_strategy": "trailing_stop",
                "trail_pct": 1.0,
                "trail_activation_pct": 1.0,
                "stop_loss_pct": 3.0,
            },
            holding_periods=_BARRIER_HOLD,
        ),
        ExitProfile(
            label="trail_1.5_2",
            hub_fields={
                "exit_strategy": "trailing_stop",
                "trail_pct": 1.5,
                "trail_activation_pct": 2.0,
                "stop_loss_pct": 3.0,
            },
            holding_periods=_BARRIER_HOLD,
        ),
        ExitProfile(
            label="breakeven",
            hub_fields={"exit_strategy": "min_profit_after_fees", "min_net_pct": 0.0},
            holding_periods=_BARRIER_HOLD,
        ),
    )


def build_full_exit_grid() -> tuple[ExitProfile, ...]:
    """Default sweep: the 2-4%/1-6% tpsl grid + all alt families."""
    return build_fixed_tpsl_exits() + build_alt_exit_families(include_extended_rr=True)


def build_core_exit_grid() -> tuple[ExitProfile, ...]:
    """Smaller slice: full tpsl grid + one alt per family (for long runs)."""
    return build_fixed_tpsl_exits() + build_alt_exit_families(include_extended_rr=False)


def build_fifo_oos_exit_grid() -> tuple[ExitProfile, ...]:
    """The canonical 81-cell honest sweep: 8x8 SL/TP (1-8%, step 1%) + 17 alt families."""
    return build_fixed_tpsl_exits(
        sl_min=_FIFO_SL_MIN, sl_max=_FIFO_SL_MAX, tp_min=_FIFO_TP_MIN, tp_max=_FIFO_TP_MAX, step=_FIFO_STEP
    ) + build_alt_exit_families(include_extended_rr=True)


#: The exit that HOLDS a stance book's position until its own signal flips (CERT-SIGNAL-EXIT-1).
#: RAW_SIGNAL closes on the OPPOSITE signal -- a move to flat does not close it -- and times out at the
#: cell's hold. For HYPOTHESIS certs only: the canonical grid above also feeds training's validation
#: backtest and every model_spec cert, which this must not change. Measured 2026-09-28: of 29 hunt books
#: whose held stance beat same-span buy-and-hold, 26 had a barrier-only cert reporting no cell doing so.
STANCE_SIGNAL_EXIT = ExitProfile(label="signal", hub_fields={"exit_strategy": "raw_signal"}, holding_periods=None)


#: The max-hold fallback of a thin-stop exit: 48 x 5m = 4 h, the owner's product spec (the cell's hold sweep
#: may still override it, as for every barrier family).
_THIN_STOP_HOLD = 48


def _thin_stop_exit(label: str, *, be_r: float, tp_r: tuple[float, ...] = (), runner_parts: int = 0, use_trail: bool = True) -> ExitProfile:
    hub: ExitHubFields = {
        "exit_strategy": "thin_stop_ladder",
        "thin_be_r": be_r,
        "thin_tp_r": tp_r,
        "thin_runner_parts": runner_parts,
        "thin_use_trail": use_trail,
    }
    return ExitProfile(label=label, hub_fields=hub, holding_periods=_THIN_STOP_HOLD)


#: The thin-stop exits graded on the 5m sweep entries (CERT-THIN-STOP-EXITS-1), each pre-registered there before
#: its result was read: the chandelier runner and 3 TP + runner at 3 / 6 / 12 R (arm 56's four cells: x breakeven
#: at 1 / 2 R) and the four-take-profit ladder at 2 / 4 / 8 / 16 R with no runner (arm 54's pick, the owner's
#: "4 TP" spec). They exist only for a book that carries its own stop column -- see build_hypothesis_exit_grid.
THIN_STOP_EXITS: tuple[ExitProfile, ...] = tuple(
    profile
    for be_r in (1.0, 2.0)
    for profile in (
        _thin_stop_exit(f"thin_be{be_r:g}_chand", be_r=be_r),
        _thin_stop_exit(f"thin_be{be_r:g}_tp3r_chand", be_r=be_r, tp_r=(3.0, 6.0, 12.0), runner_parts=1),
        _thin_stop_exit(f"thin_be{be_r:g}_tp4", be_r=be_r, tp_r=(2.0, 4.0, 8.0, 16.0), use_trail=False),
    )
)


def build_hypothesis_exit_grid(*, thin_stop: bool = False) -> tuple[ExitProfile, ...]:
    """The canonical 81-cell grid plus the stance-held exit -- for books that emit a stance, not a probability.

    ``thin_stop`` adds ``THIN_STOP_EXITS``: only a book that hands the engine its own per-signal stop column can
    take them (``backtester_exit_thin_stop.frame_carries_thin_stop``); every other book's grid is unchanged.
    """
    base = (*build_fifo_oos_exit_grid(), STANCE_SIGNAL_EXIT)
    if thin_stop:
        return (*base, *THIN_STOP_EXITS)
    return base


def filter_exit_grid_for_leverage(grid: tuple[ExitProfile, ...], leverage: int) -> tuple[ExitProfile, ...]:
    """Drop exit profiles whose stop-loss can't trigger before liquidation at ``leverage``.

    An 8% stop is valid at 3x but impossible at 100x (liquidated at ~1%), so sweeping it there
    would score a stop that never fires. Profiles with no explicit ``stop_loss_pct`` are always
    kept; spot / low leverage (no cap) returns the grid unchanged. SL side only — take-profit is a
    favorable move and is never liquidation-capped.
    """
    cap = max_sl_pct_for_leverage(leverage)
    if cap is None:
        return grid
    return tuple(profile for profile in grid if float(profile.hub_fields.get("stop_loss_pct") or 0.0) <= cap)
