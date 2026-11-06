"""A typed ``@njit(cache=True)``: the kernel keeps its own signature, so it needs no mypy suppression comment.

IMPORTERS/CALLERS: src/infrastructure/ml/backtester_exit_thin_stop.py (the first adopter, 2026-10-15). The numba_*
feature modules still silence mypy's untyped-decorator error on each kernel and adopt this when next touched.
AFFECTED API: none -- the kernel is the same numba Dispatcher, compiled with the same on-disk cache; jit_inlined (new
2026-10-19, indicators.rsi's zero-loss helper) for a helper only kernels call.
DATA SCHEMAS: none.

WHY: numba's ``njit`` is untyped on the local wheel and typed on CI's (pyproject's numba override records the
measurement), so every kernel carried a suppression whose necessity depended on the machine. Here the one untyped call
sits in one place, excluded by name in pyproject (``untyped_calls_exclude``), and every kernel keeps its own signature.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, cast

import numba
import numba.extending

type _Decorator = Callable[[Callable[..., object]], Callable[..., object]]
#: numba's two decorators, their types written down once at the boundary (the local wheel ships none -- WHY above).
_NJIT: Final = cast("Callable[..., _Decorator]", numba.njit)
_REGISTER_JITABLE: Final = cast("_Decorator", numba.extending.register_jitable)


def njit_cached[F: Callable[..., object]](fn: F) -> F:
    """``fn`` compiled by numba in nopython mode with its on-disk cache, typed as ``fn`` itself."""
    return cast("F", _NJIT(cache=True)(fn))


def jit_inlined[F: Callable[..., object]](fn: F) -> F:
    """``fn`` callable from numba-compiled code, compiled INTO each caller -- so it has no dispatcher of its own for a
    prewarm to miss -- and from Python as itself (numba's ``register_jitable``, typed as ``fn``)."""
    return cast("F", _REGISTER_JITABLE(fn))
