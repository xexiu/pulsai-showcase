"""The out-of-sample window as one value, and the tiered gate that takes it.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.

``evaluate_oos_window_gate`` is THE tiered OOS gate (the eleven-argument ``evaluate_oos_tiered_gate`` it replaced is
deleted). The grading it inherited is pinned on hand-picked cases for every label AND on a seeded sweep whose digest was
taken from the old function on 2026-10-06 (P1-9g final step), so the move can never have changed a label.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import date, timedelta
from typing import Any

import numpy as np
import pytest

from src.shared.math.backtest_validation_statistics import (
    estimate_oos_bars,
    format_oos_gate_tier,
    resolve_research_min_trades,
)
from src.shared.math.oos_window import OosWindow, evaluate_oos_window_gate

_SEED = 20261005
_SWEEP = 300
_TIMEFRAMES = ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d")
#: sha256 of the old gate's verdicts on the sweep, floats at 9 significant digits (`_platform_independent`).
#:
#: It was the sha256 of the bare repr() (2fd41a1d...28f2b1), taken on macOS arm64. A repr carries every float to
#: its last bit, and CI's Linux x86_64 runner computes deflated_sharpe ~1 ULP apart on the same locked numpy/scipy
#: (libm and SIMD differ), so the digest went red there with no label moved. Re-derived 2026-10-07 on the machine
#: that still reproduced 2fd41a1d bit for bit -- i.e. from verdicts identical to the old gate's -- so this digest
#: pins the same verdicts; only the float noise below 1e-9 is dropped. Labels, counts and flags stay exact.
_SWEEP_DIGEST = "35a812c700402fdc77bafd8fa1db3503b4f2c2436aff38ea1481e5e0ae8a0e6f"
_SPRING = OosWindow(timeframe="1d", start="2026-03-02", end="2026-06-08")

#: One case per label the gate can produce, on a 98-day 1d window (research floor 30, cert 200).
_LABELLED_CASES: dict[str, dict[str, Any]] = {
    "cert": {"net": 40.0, "profit_factor": 1.9, "num_trades": 240, "observed_sharpe": 2.2, "n_trials": 3, "trial_sharpe_std": 0.2},
    "research": {"net": 18.0, "profit_factor": 1.6, "num_trades": 40, "observed_sharpe": 2.2, "n_trials": 3, "trial_sharpe_std": 0.2},
    "scout": {"net": 5.0, "profit_factor": 1.2, "num_trades": 5, "observed_sharpe": 0.5, "n_trials": 3, "trial_sharpe_std": 0.2},
    "kill": {"net": -5.0, "profit_factor": 0.8, "num_trades": 40, "observed_sharpe": 2.0, "n_trials": 3, "trial_sharpe_std": 0.2},
}


def _seeded_sweep() -> list[tuple[OosWindow, dict[str, Any]]]:
    """Every timeframe, empty and inverted windows (every 13th), PF exactly 1 or 0 (every 9th), zero dispersion (every 5th)."""
    rng = np.random.default_rng(_SEED)
    cases: list[tuple[OosWindow, dict[str, Any]]] = []
    for i in range(_SWEEP):
        start = date(2022, 1, 1) + timedelta(days=int(rng.integers(0, 1500)))
        span = int(rng.choice([-5, 0, 1])) if i % 13 == 0 else int(rng.integers(1, 1100))
        window = OosWindow(timeframe=str(rng.choice(_TIMEFRAMES)), start=start.isoformat(), end=(start + timedelta(days=span)).isoformat())
        kwargs: dict[str, Any] = {
            "net": float(rng.uniform(-60.0, 150.0)),
            "profit_factor": float(rng.choice([1.0, 0.0])) if i % 9 == 0 else float(rng.uniform(0.2, 3.5)),
            "num_trades": int(rng.integers(0, 2000)),
            "observed_sharpe": float(rng.uniform(-2.0, 4.0)),
            "n_trials": int(rng.integers(1, 3000)),
            "trial_sharpe_std": 0.0 if i % 5 == 0 else float(rng.uniform(0.0, 1.5)),
        }
        if rng.random() < 0.3:
            kwargs["research_min_trades_override"] = int(rng.integers(1, 300))
        cases.append((window, kwargs))
    return cases


def _platform_independent(value: object) -> object:
    """A verdict with every float at 9 significant digits; ints, bools, strings and structure untouched."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__, tuple((f.name, _platform_independent(getattr(value, f.name))) for f in dataclasses.fields(value)))
    if isinstance(value, float):
        return format(value, ".9g")
    if isinstance(value, tuple | list):
        return tuple(_platform_independent(item) for item in value)
    return value


class TestTheWindowedGateKeepsTheGradingItInherited:
    @pytest.mark.parametrize("label", sorted(_LABELLED_CASES))
    def test_each_label_is_reached(self, label: str) -> None:
        windowed = evaluate_oos_window_gate(window=_SPRING, **_LABELLED_CASES[label])
        assert format_oos_gate_tier(windowed, exploratory_pass=False) == label

    def test_a_seeded_sweep_moves_no_verdict(self) -> None:
        graded = [repr(_platform_independent(evaluate_oos_window_gate(window=window, **kwargs))) for window, kwargs in _seeded_sweep()]
        assert hashlib.sha256("\n".join(graded).encode()).hexdigest() == _SWEEP_DIGEST

    def test_the_sweep_is_not_vacuous(self) -> None:
        """A sweep whose cases all land on one label would prove nothing about the others."""
        labels = {format_oos_gate_tier(evaluate_oos_window_gate(window=w, **k), exploratory_pass=False) for w, k in _seeded_sweep()}
        assert {"cert", "scout", "kill"} <= labels


class TestTheWindowSetsTheResearchFloor:
    def test_the_floor_is_scaled_from_the_window_bars(self) -> None:
        verdict = evaluate_oos_window_gate(window=_SPRING, **_LABELLED_CASES["research"])
        bars = estimate_oos_bars(timeframe="1d", start_date="2026-03-02", end_date="2026-06-08")
        assert verdict.oos_bars == bars
        assert verdict.min_trades_research == resolve_research_min_trades(bars) == 30

    def test_a_longer_window_demands_more_trades(self) -> None:
        long_window = dataclasses.replace(_SPRING, start="2023-03-02")
        short = evaluate_oos_window_gate(window=_SPRING, **_LABELLED_CASES["research"])
        long = evaluate_oos_window_gate(window=long_window, **_LABELLED_CASES["research"])
        assert long.min_trades_research > short.min_trades_research
        assert long.research_pass is False

    def test_an_override_replaces_the_window_floor(self) -> None:
        verdict = evaluate_oos_window_gate(window=_SPRING, research_min_trades_override=10, **_LABELLED_CASES["research"])
        assert verdict.min_trades_research == 10


class TestTheWindowIsAValue:
    def test_two_windows_with_the_same_fields_are_equal(self) -> None:
        assert OosWindow(timeframe="4h", start="2026-01-01", end="2026-02-01") == OosWindow(timeframe="4h", start="2026-01-01", end="2026-02-01")

    @pytest.mark.parametrize("field", ["timeframe", "start", "end"])
    def test_a_window_cannot_be_changed_after_it_is_built(self, field: str) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(_SPRING, field, "2026-01-01")
