"""Action-anchored target price computation for the AI signal-explain Conclusion line.

Single source of truth for "given a signal's action + current price + the
model_input_features dict containing dist_to_support_N / dist_to_resistance_N,
what target price should the Conclusion line cite?". Consumed by:

- ``MockAIProvider._extract_price_for_conclusion`` — emits a deterministic
  per-action target so the mock is useful in dev without a real LLM.
- (Future) any tooling that wants to render the same target outside of the
  AI explain flow (e.g. signal cards, trade builder).

The real LLM is also instructed to follow the same rule via the prompt in
``ai_provider_base``, so the produced Conclusion shape is identical
across providers.

Why this isn't inline in the mock: the rule is a semantic invariant of
the explain feature, not a mock-specific detail. Inlining it would
duplicate logic between mock and any future user-facing surface that
wants to display "where the signal expects the price to go".

The ``dist_to_*_N`` fields are emitted as percentages (e.g. ``0.42`` means
the price is 0.42% below the nearest resistance), so:

- BUY  target = current_price * (1 + |dist_to_resistance| / 100)
- SELL target = current_price * (1 - |dist_to_support|    / 100)
- HOLD target = current_price (no directional anchor — explain stays where it is)

Sign convention from ``feature_patterns.py``:
- ``dist_to_resistance_N = (close - resistance_N) / resistance_N * 100`` → typically NEGATIVE
  (close is below resistance).
- ``dist_to_support_N = (close - support_N) / support_N * 100`` → typically POSITIVE
  (close is above support).
So we take ``abs(...)`` to get the gap magnitude regardless of sign.
"""

from __future__ import annotations

import math
from typing import Any

from src.domain.enums import SignalAction


def compute_target_price_for_action(
    action: SignalAction | str,
    current_price: float,
    model_input_features: dict[str, Any] | None,
) -> float:
    """Resolve the Conclusion-line target price for a signal action.

    Falls back to ``current_price`` whenever the feature vector is missing,
    sparse, or non-numeric — never raises. The Conclusion line is a
    display-only field, so a missing-data path must NOT crash the explain
    endpoint; it just degrades to a flat HOLD-style target.

    Args:
        action: Signal action (``SignalAction`` or its string value).
        current_price: Snapshot price at signal time (positive float).
        model_input_features: Per-bar feature vector from the ML model.
            May be ``None`` or missing the ``dist_to_*`` keys.

    Returns:
        Positive float target price. Falls back to ``current_price`` for
        HOLD, unknown actions, missing data, non-finite intermediates,
        or non-positive outcomes.
    """
    if current_price <= 0 or not math.isfinite(current_price):
        return max(current_price, 0.0)

    action_value = action.value if isinstance(action, SignalAction) else str(action).upper()

    if action_value == SignalAction.HOLD.value:
        return current_price

    features = model_input_features or {}

    if action_value == SignalAction.BUY.value:
        gap_pct = _resolve_signed_gap_pct(features, _RESISTANCE_KEYS)
        candidate = current_price * (1.0 + gap_pct / 100.0)
        return candidate if candidate > 0 and math.isfinite(candidate) else current_price

    if action_value == SignalAction.SELL.value:
        gap_pct = _resolve_signed_gap_pct(features, _SUPPORT_KEYS)
        candidate = current_price * (1.0 - gap_pct / 100.0)
        return candidate if candidate > 0 and math.isfinite(candidate) else current_price

    # Unknown action string — degrade safely to current price.
    return current_price


# Resistance keys ordered by lookback (shorter window first; falls through if
# missing/non-finite). Mirrors the feature emitter order in
# ``src/domain/services/features/feature_patterns.py``.
_RESISTANCE_KEYS: tuple[str, ...] = ("dist_to_resistance_5", "dist_to_resistance_20")
_SUPPORT_KEYS: tuple[str, ...] = ("dist_to_support_5", "dist_to_support_20")


def _resolve_signed_gap_pct(features: dict[str, Any], keys: tuple[str, ...]) -> float:
    """Return the first finite, non-zero gap percentage from ``keys`` (abs value).

    Walks ``keys`` in order and returns the magnitude of the first one that
    parses as a finite number. ``0.0`` when no key produces a usable value.
    """
    for key in keys:
        raw = features.get(key)
        if not isinstance(raw, (int, float)):
            continue
        value = float(raw)
        if not math.isfinite(value) or value == 0.0:
            continue
        return abs(value)
    return 0.0
