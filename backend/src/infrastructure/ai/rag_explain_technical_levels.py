"""
Technical-levels block of the signal-explain RAG context.

IMPORTERS/CALLERS: rag_explain_signal_sections (section registry), tests/unit/infrastructure/ai/test_technical_levels_*.
AFFECTED API: none (prompt text only).
DATA SCHEMAS: none.

Split out of rag_explain_signal_sections.py (P1-8b) to respect module line limits.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

from src.domain.enums import SignalAction
from src.shared.constants.ai_explain_conclusion import TECHNICAL_LEVEL_FEATURE_KEYS

logger = logging.getLogger(__name__)


def _render_relative_pct_resistance_line(key: str, raw_value: float, price: float) -> str:
    level_price = price * (1.0 + abs(raw_value) / 100.0)
    return f"- Nearest resistance ({key.rsplit('_', maxsplit=1)[-1]}-bar): ~${level_price:,.2f} ({raw_value:+.2f}% from price)"


def _render_relative_pct_support_line(key: str, raw_value: float, price: float) -> str:
    level_price = price * (1.0 - abs(raw_value) / 100.0)
    return f"- Nearest support ({key.rsplit('_', maxsplit=1)[-1]}-bar): ~${level_price:,.2f} ({raw_value:+.2f}% from price)"


def _render_atr_line(key: str, raw_value: float, _price: float) -> str:
    return f"- ATR ({key.rsplit('_', maxsplit=1)[-1]}-bar): {raw_value:.4f} (volatility band width)"


def _render_bb_width_line(_key: str, raw_value: float, _price: float) -> str:
    return f"- Bollinger Band width: {raw_value:.4f} (volatility regime)"


def _offset_pct(price: float, level: float) -> float:
    return ((level - price) / price) * 100.0 if price > 0 else 0.0


def _absolute_level_renderer(label: str) -> Callable[[str, float, float], str]:
    """Build a renderer for absolute-price feature keys (Keltner, CP, …)."""

    def render(_key: str, raw_value: float, price: float) -> str:
        return f"- {label}: ~${raw_value:,.2f} ({_offset_pct(price, raw_value):+.2f}% from price)"

    return render


# Renderer dispatch — keeps ``format_technical_levels_block`` simple (cyclomatic
# complexity below the ruff C901 ceiling) and centralizes how each feature key
# maps to its rendered line. Exact-match keys win over prefix predicates.
_EXACT_KEY_RENDERERS: dict[str, Callable[[str, float, float], str]] = {
    "bb_width": _render_bb_width_line,
    "keltner_upper": _absolute_level_renderer("Keltner upper (ATR-anchored resistance)"),
    "keltner_lower": _absolute_level_renderer("Keltner lower (ATR-anchored support)"),
    "cp_resistance_line": _absolute_level_renderer("CP resistance (chart pattern)"),
    "cp_support_line": _absolute_level_renderer("CP support (chart pattern)"),
    "cp_target": _absolute_level_renderer("CP target (pattern measured move)"),
    "cp_stop_loss": _absolute_level_renderer("CP stop-loss (pattern invalidation)"),
}
_PREFIX_RENDERERS: tuple[tuple[str, Callable[[str, float, float], str]], ...] = (
    ("dist_to_resistance", _render_relative_pct_resistance_line),
    ("dist_to_support", _render_relative_pct_support_line),
    ("atr_", _render_atr_line),
)


def _render_technical_level_line(key: str, raw_value: float, price: float) -> str | None:
    """Pick the right renderer for ``key`` from the dispatch tables."""
    exact = _EXACT_KEY_RENDERERS.get(key)
    if exact is not None:
        return exact(key, raw_value, price)
    for prefix, renderer in _PREFIX_RENDERERS:
        if key.startswith(prefix):
            return renderer(key, raw_value, price)
    return None


def format_technical_levels_block(
    current_price: float | None,
    model_input_features: dict[str, Any] | None,
    action: str | None,
) -> str | None:
    """Render BUY/SELL target prices anchored on real support/resistance gaps.

    The chart-display feature vector already carries ``dist_to_support_N`` /
    ``dist_to_resistance_N`` (% offsets from the nearest S/R level over an
    N-bar lookback). Without this section the LLM/mock had no anchor for
    a BUY/SELL Conclusion target other than the entry price — producing
    misleading "target = entry" outputs. This section makes the anchors
    explicit so the Conclusion line can cite real levels.

    Returns ``None`` when ``current_price`` is missing or the feature dict
    holds none of the keys we display.
    """
    if not isinstance(current_price, (int, float)) or current_price <= 0:
        logger.debug("format_technical_levels_block: skipped (no usable price or level features)")
        return None
    features = model_input_features or {}

    relevant: list[tuple[str, float]] = []
    for key in TECHNICAL_LEVEL_FEATURE_KEYS:
        raw = features.get(key)
        if isinstance(raw, (int, float)):
            value = float(raw)
            if math.isfinite(value):
                relevant.append((key, value))
    if not relevant:
        return None

    price = float(current_price)
    lines = [
        "## Technical levels (action-anchored targets)",
        f"- Snapshot price: ${price:,.2f}",
    ]

    for key, raw_value in relevant:
        rendered = _render_technical_level_line(key, raw_value, price)
        if rendered is not None:
            lines.append(rendered)

    # Spell out the per-action target rule for the LLM so the Conclusion
    # line cites the right level. Mock provider follows the same rule
    # via ``compute_target_price_for_action``.
    if action:
        action_norm = str(action).upper()
        if action_norm == SignalAction.BUY.value:
            lines.append("- BUY target rule: cite the nearest resistance level above as the Conclusion target.")
        elif action_norm == SignalAction.SELL.value:
            lines.append("- SELL target rule: cite the nearest support level below as the Conclusion target.")
        elif action_norm == SignalAction.HOLD.value:
            lines.append("- HOLD target rule: cite the current snapshot price (no directional target).")

    return "\n".join(lines)
