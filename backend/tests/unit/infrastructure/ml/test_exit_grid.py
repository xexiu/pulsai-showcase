"""Behavior tests for the SoT exit grid (relocated from src/research to src).

Guards the canonical cell counts + percent units so the honest sweep + registry can rely
on a stable grid, and so the research re-export can't silently drift from production.
"""

from __future__ import annotations

from src.infrastructure.ml.exit_grid import (
    ExitProfile,
    build_alt_exit_families,
    build_fifo_oos_exit_grid,
    build_fixed_tpsl_exits,
    build_full_exit_grid,
)


def test_fifo_grid_has_81_cells() -> None:
    grid = build_fifo_oos_exit_grid()
    assert len(grid) == 81  # 8x8 tpsl (64) + 17 alt families
    assert all(isinstance(p, ExitProfile) for p in grid)


def test_full_grid_has_35_cells() -> None:
    # defaults: SL {2,3,4} x TP {1..6} = 18 tpsl + 17 alts
    assert len(build_full_exit_grid()) == 35


def test_fixed_tpsl_percent_units_and_labels() -> None:
    exits = build_fixed_tpsl_exits(sl_min=1.0, sl_max=2.0, tp_min=1.0, tp_max=2.0, step=1.0)
    assert len(exits) == 4  # 2x2
    by_label = {e.label: e for e in exits}
    assert "tpsl_2_2" in by_label
    p = by_label["tpsl_2_2"]
    assert p.hub_fields["stop_loss_pct"] == 2.0  # percent: 2.0 == 2%
    assert p.hub_fields["take_profit_pct"] == 2.0
    assert p.hub_fields["exit_strategy"] == "fixed_tpsl"


def test_half_percent_step_makes_finer_grid() -> None:
    # SL {1,1.5,2} x TP {1,1.5,2} = 9 (the 0.5% step the registry will default to)
    exits = build_fixed_tpsl_exits(sl_min=1.0, sl_max=2.0, tp_min=1.0, tp_max=2.0, step=0.5)
    assert len(exits) == 9


def test_alt_families_cover_all_exit_strategies() -> None:
    labels = {e.label for e in build_alt_exit_families(include_extended_rr=True)}
    assert {"hold", "trail_1_1", "breakeven", "atr_x2", "dyn_tpsl_x2"}.issubset(labels)
