"""
Research-only forward-return horizon grids per timeframe (bars).

Keys MUST exist in ``TIMEFRAME_REGISTRY``. Consumed by indicator IC research scripts.

@see apps/api/src/research/titancharts_indicator_phase1_ic.py
"""

from __future__ import annotations

from src.shared.constants.timeframes import TIMEFRAME_REGISTRY

IC_HORIZON_GRID_BY_TIMEFRAME: dict[str, tuple[int, ...]] = {
    # 1m (LTF since 2026-10-11): 5m's grid scaled by bars-per-day (x5) -- the same 30 min / 1 h / 2 h
    # wall-clock horizons, all inside the owner's 240-bar (4 h) 1m max hold.
    "1m": (30, 60, 120),
    "5m": (6, 12, 24),
    "15m": (4, 8, 16),
    "30m": (4, 8, 12),
    "1h": (6, 12, 24),
    # 2h/6h chosen to cover the same WALL-CLOCK horizons as their neighbours, which is what these
    # grids are really expressing: 2h → 8h/16h/32h (between 1h's 6/12/24h and 4h's 12/24/48h),
    # 6h → 12h/24h/48h (between 4h's 12/24/48h and 8h's 16/32/64h).
    "2h": (4, 8, 16),
    "4h": (3, 6, 12),
    "6h": (2, 4, 8),
    "8h": (2, 4, 8),
    "12h": (2, 4, 6),
    "1d": (2, 5, 10),
    "3d": (2, 4, 8),
}

_unknown = set(IC_HORIZON_GRID_BY_TIMEFRAME.keys()) - set(TIMEFRAME_REGISTRY.keys())
if _unknown:
    raise ValueError(f"IC_HORIZON_GRID_BY_TIMEFRAME has unknown registry keys: {sorted(_unknown)}")
