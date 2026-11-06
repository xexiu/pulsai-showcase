"""Redis cache SoT for liquidation heatmap chart overlay snapshots."""

from __future__ import annotations

from typing import Final

LIQUIDATION_HEATMAP_CACHE_KEY_PREFIX: Final[str] = "liquidation-heatmap:"

# Placeholder until leverage/min-liq/grouping filters ship (Phase 2 FE prefs).
LIQUIDATION_HEATMAP_DEFAULT_FILTER_HASH: Final[str] = "default"
