"""Env-var resolvers shared by the constants modules — the SoT for "read a setting, or fall back".

REUSE-AUDIT: searched `src/shared/constants/` for an existing env / resolve / coerce helper before
writing this — there was none. This consolidates four files' worth of copies rather than adding a
fifth.

WHY IT EXISTS. `analyze(kind="clones")` on 2026-08-26 reported two similarity-1.00 clusters:

    _resolve_positive_int / _resolve_non_negative_int / _resolve_non_negative_float
        ohlcv_sources.py, signal_freshness.py, spike_alert.py
    _resolve_positive_float
        observability_metrics.py, ohlcv_sources.py

The same bodies written out repeatedly inside the very modules whose job is to be the single source
of truth for settings. The owner named this shape exactly: *"a CONST bla can be repeted in lots of
files instead of SoT."* The fourth file (`observability_metrics.py`) was found by the pre-write
clone guard, not by grep — a name search for `_resolve_positive_int` never reaches a module that
only copied the float one.

ONE KERNEL, FOUR WRAPPERS. Writing four near-identical resolvers here would have re-created the
cluster one directory over, in the file meant to remove it. So read/parse/floor lives once in
:func:`_resolve_number`; the public four exist for their type signature (a caller wanting an int
must not be handed a float) and for a readable call site.

Every resolver has the same contract: **a missing, malformed, or out-of-range value yields the
default.** Config never makes a process fail to start — a typo in an env var degrades to the
documented default rather than crashing a worker at import time.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping


def env_source(env: Mapping[str, str] | None) -> Mapping[str, str]:
    """The mapping to read from: an explicit one, else the real process environment.

    Production callers pass ``None``; the injectable mapping is what makes every setting testable
    without mutating global state.
    """
    return os.environ if env is None else env


def _resolve_number[Number: (int, float)](
    *,
    env: Mapping[str, str] | None,
    var: str,
    default: Number,
    cast: Callable[[str], Number],
    minimum: Number,
) -> Number:
    """Read ``var``, cast it, and keep it only if it meets ``minimum``; otherwise ``default``."""
    raw = env_source(env).get(var)
    if raw is None:
        return default
    try:
        value = cast(raw)
    except TypeError, ValueError:
        return default
    return value if value >= minimum else default


#: The spellings of yes and no this codebase accepts in an env var.
#:
#: Lifted verbatim from ``spike_alert.resolve_spike_watch_enabled``, which had them inline. A
#: SECOND copy is exactly the clone this module exists to remove -- see the docstring above --
#: and a bool parser is the one resolver most likely to be re-invented as a bare truthy check,
#: which reads ``FLAG=0`` as YES.
_TRUE_TOKENS: frozenset[str] = frozenset({"1", "true", "yes", "on"})
_FALSE_TOKENS: frozenset[str] = frozenset({"0", "false", "no", "off"})


def resolve_bool(*, env: Mapping[str, str] | None, var: str, default: bool) -> bool:
    """Resolve a boolean env var; missing, blank or unrecognised yields ``default``.

    Same contract as every resolver here: config never crashes a process. Note what that means
    for a permission flag -- pass ``default=False`` and an unparseable value fails CLOSED, which
    is the right reading for a variable whose job is to make a hazard deliberate.
    """
    raw = env_source(env).get(var)
    if raw is None:
        return default
    token = raw.strip().lower()
    if token in _TRUE_TOKENS:
        return True
    if token in _FALSE_TOKENS:
        return False
    return default


def resolve_positive_int(*, env: Mapping[str, str] | None, var: str, default: int) -> int:
    """Read a strictly-positive int env var; missing/invalid/<1 → default."""
    return _resolve_number(env=env, var=var, default=default, cast=int, minimum=1)


def resolve_non_negative_int(*, env: Mapping[str, str] | None, var: str, default: int) -> int:
    """Read a non-negative int env var; missing/invalid/<0 → default (0 allowed)."""
    return _resolve_number(env=env, var=var, default=default, cast=int, minimum=0)


def resolve_non_negative_float(*, env: Mapping[str, str] | None, var: str, default: float) -> float:
    """Read a non-negative float env var; missing/invalid/<0 → default (0 allowed)."""
    return _resolve_number(env=env, var=var, default=default, cast=float, minimum=0.0)


def resolve_positive_float(*, env: Mapping[str, str] | None, var: str, default: float) -> float:
    """Read a strictly-positive float env var; missing/invalid/<=0 → default.

    The floor is EXCLUSIVE here, unlike the int case where "strictly positive" and ">= 1" coincide.
    A float setting of 0.001 is meaningful (a rate, a fraction of a second), so this cannot reuse
    the shared ``>= minimum`` comparison and keeps its own guard.
    """
    raw = env_source(env).get(var)
    if raw is None:
        return default
    try:
        value = float(raw)
    except TypeError, ValueError:
        return default
    return value if value > 0 else default


__all__ = [
    "env_source",
    "resolve_bool",
    "resolve_non_negative_float",
    "resolve_non_negative_int",
    "resolve_positive_float",
    "resolve_positive_int",
]
