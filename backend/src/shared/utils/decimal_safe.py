"""Safe coercion helpers for untrusted numeric payloads (CCXT dicts, env, JSON).

Single source of truth replacing duplicated ``_decimal_or_none`` / ``_int_or_none``
helpers that previously lived in
- ``src/domain/services/ccxt_fee_hints.py``
- ``src/infrastructure/exchange/adapters/bitget_futures.py``

Both callers need the same guarantee: *never* raise on garbage input; return
``None`` when the value cannot be represented, so caller logic can fall through
to defaults or mark a field unknown. We do **not** use these helpers for
user-facing validation (Pydantic / Valibot own that); these are for adapter-layer
normalization.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

__all__ = ["decimal_or_none", "float_or_none", "int_or_none", "positive_decimal_or_none"]


def decimal_or_none(value: Any) -> Decimal | None:
    """Coerce any JSON-ish scalar to `Decimal`; return ``None`` on failure.

    Uses ``Decimal(str(value))`` to avoid binary-float drift (``0.1`` stays
    ``Decimal("0.1")``, not ``Decimal("0.1000000000000000055511151231257827021181583404541015625")``).
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError, TypeError, ValueError:
        return None


def positive_decimal_or_none(value: Any) -> Decimal | None:
    """Coerce to :class:`Decimal` and return only when strictly positive.

    Thin wrapper over :func:`decimal_or_none` for the very common adapter-layer
    pattern "accept the value iff it represents a real, usable positive number"
    (e.g. a ticker field where zero / negative / junk should collapse to
    ``None`` so callers fall through to defaults).
    """
    coerced = decimal_or_none(value)
    if coerced is None or coerced <= 0:
        return None
    return coerced


def float_or_none(value: Any) -> float | None:
    """Coerce any JSON-ish scalar to ``float``; return ``None`` on failure.

    Differs from ``float(value)`` in two ways the Redis-snapshot codecs depend on:
    - ``None`` stays ``None`` (instead of raising).
    - ``bool`` returns ``None`` (Python's ``bool`` is a subclass of ``int``, so
      a stray JSON ``true`` would otherwise silently coerce to ``1.0`` and
      poison a numeric field).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def int_or_none(value: Any) -> int | None:
    """Coerce any JSON-ish scalar to ``int``; return ``None`` on failure.

    Tolerates decimal strings (e.g. CCXT returning ``"125.0"`` for max leverage)
    by going through ``Decimal`` on the fallback path.

    ``bool`` returns ``None`` for the same reason ``float_or_none`` rejects it:
    ``bool`` subclasses ``int``, so a stray JSON ``true`` would read as the
    count ``1`` and an UNMEASURED field would become a measured one.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        try:
            return int(Decimal(str(value)))
        except ArithmeticError, TypeError, ValueError:
            return None


def int_or_default(value: Any, default: int = 0) -> int:
    """Coerce a JSON-ish scalar to ``int``, falling back to ``default``.

    Sibling of :func:`int_or_none`, not a duplicate of it. Two contracts differ deliberately:

    * this one always returns an ``int`` — callers reading config/artifact payloads want a usable
      number, not another ``None`` to branch on;
    * a ``bool`` is NOT a number here. ``int(True) == 1`` is true in Python and wrong in these
      call-sites, where a JSON ``true`` in an int field means the payload is malformed, not that
      the value is one.
    """
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default
