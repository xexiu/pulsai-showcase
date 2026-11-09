"""
Serialization Utilities

Provides dynamic, DRY-compliant serialization for dataclasses.
Handles common types: datetime, enums, optional fields.

WHY this exists (per .cursorrules DRY principle):
- Dataclass fields change often (new metrics, configs, etc.)
- Hardcoded to_dict() methods require manual sync
- This utility auto-handles all fields dynamically

@see .cursorrules - DRY violations section
"""

from __future__ import annotations

import json
import math
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np


def dataclass_to_dict(
    obj: Any,
    *,
    exclude: set[str] | None = None,
    include_none: bool = True,
) -> dict[str, Any]:
    """
    DYNAMICALLY convert a dataclass to a JSON-serializable dictionary.

    Handles common types that need special serialization:
    - datetime → ISO format string
    - Enum → .value
    - Nested dataclasses → recursive conversion
    - Optional fields → included/excluded based on include_none

    Args:
        obj: A dataclass instance
        exclude: Set of field names to exclude from output
        include_none: If False, exclude fields with None values

    Returns:
        Dictionary with all fields (minus excluded) JSON-serializable

    Raises:
        TypeError: If obj is not a dataclass

    Example:
        @dataclass
        class ModelMetadata:
            version: int
            created_at: datetime
            is_production: bool = False

        metadata = ModelMetadata(version=1, created_at=datetime.now(tz=UTC))
        data = dataclass_to_dict(metadata)
        # {"version": 1, "created_at": "2026-01-27T...", "is_production": False}

        # Exclude fields
        data = dataclass_to_dict(metadata, exclude={"is_production"})
        # {"version": 1, "created_at": "2026-01-27T..."}
    """
    if not is_dataclass(obj):
        msg = f"Expected dataclass, got {type(obj).__name__}"
        raise TypeError(msg)

    exclude = exclude or set()
    result: dict[str, Any] = {}

    for field in fields(obj):
        # Skip excluded fields
        if field.name in exclude:
            continue

        value = getattr(obj, field.name)

        # Handle None values
        if value is None:
            if include_none:
                result[field.name] = None
            continue

        # Convert value to JSON-serializable format
        result[field.name] = _serialize_value(value)

    return result


def _normalize_scalar(value: Any) -> tuple[bool, Any]:
    """
    Normalize a scalar value to JSON-safe Python primitive.

    Handles NaN/Inf → None, numpy scalars → Python primitives.

    Returns:
        (was_handled, result) — if was_handled is True, use result directly.
    """
    # NaN/Inf floats → None (RFC 8259: NaN/Inf are invalid JSON)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return True, None
        return True, value

    # numpy scalar types → Python primitives
    # WHY: json.dumps(np.float64(3.14)) raises TypeError
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return True, None
        return True, float(value)
    if isinstance(value, np.integer):
        return True, int(value)
    if isinstance(value, np.bool_):
        return True, bool(value)

    # Decimal / UUID — common in API schemas and audit payloads; SQLAlchemy JSON
    # uses json.dumps without a default= handler.
    if isinstance(value, Decimal | UUID):
        return True, str(value)

    return False, value


def sanitize_scalar_for_json(value: Any) -> Any:
    """
    Normalize one scalar value to a JSON-safe primitive when possible.

    Intended for call sites that already iterate scalar series values and do not
    need the recursive collection handling of ``sanitize_for_json()``.
    """
    handled, result = _normalize_scalar(value)
    if handled:
        return result
    return value


def round_finite(value: float, digits: int) -> float | None:
    """Round a finite number for JSON dumps; NaN/Inf become None (RFC 8259).

    Do not coerce Spearman NaN to 0.0 — that value would read as measured
    zero correlation. Non-finite inputs stay None so Valibot nullable(number)
    on rank_ic can distinguish missing from zero (LoopEngineeringPanel fmt
    renders null as an em-dash, not 0.000).
    """
    as_float = float(value)
    if not math.isfinite(as_float):
        return None
    return round(as_float, digits)


def load_json_str_list(
    path: Path,
    key: str,
    *,
    required: bool = True,
    missing_hint: str = "",
) -> list[str]:
    """Read a JSON object and return payload[key] as a list of strings.

    Frozen research features.json uses feature_names. Overlay probes that
    fall back to a built-in column set pass required=False.
    """
    if not path.is_file():
        if not required:
            return []
        suffix = ""
        if missing_hint:
            suffix = f" — {missing_hint}"
        raise FileNotFoundError(f"missing {path}{suffix}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object at {path}, got {type(payload).__name__}")
    if required:  # noqa: SIM108 — explicit doors; required KeyError vs optional empty list
        raw = payload[key]
    else:
        raw = payload.get(key) or []
    if isinstance(raw, str):
        raise TypeError(f"{key!r} at {path} must be a list of strings, got str")
    return [str(item) for item in raw]


def _serialize_value(value: Any) -> Any:
    """
    Recursively serialize a value to JSON-compatible format.

    Handles: NaN/Inf, numpy scalars, datetime, Enum, nested dataclasses,
    lists/tuples, dicts, and primitives.
    """
    # Scalars: float NaN/Inf, numpy types
    handled, result = _normalize_scalar(value)
    if handled:
        return result

    # datetime is a subclass of date
    if isinstance(value, date):
        return value.isoformat()

    # Enum → value
    if isinstance(value, Enum):
        return value.value

    # Nested dataclass → recursive
    if is_dataclass(value) and not isinstance(value, type):
        return dataclass_to_dict(value)

    # Collections → recursive
    if isinstance(value, list | tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}

    # Primitives (int, str, bool) → as-is
    return value


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize a Python object for strict JSON compliance.

    WHY this exists:
    - json.dumps(float("nan")) produces "NaN" — INVALID JSON per RFC 8259
    - numpy types (float64, int64, bool_) are not JSON-serializable
    - Decimal / UUID / date / Enum — not handled by the stdlib JSON encoder
    - storage_backends.py used default=str, silently converting NaN to "nan" string

    WHY None (not 0.0):
    - NaN = "unknown", not "zero" — None preserves semantic meaning
    - Frontend/consumers decide display (e.g., "N/A", "-", skip)

    Args:
        obj: Any Python object (dict, list, scalar, etc.)

    Returns:
        JSON-safe version of the object

    Example:
        >>> sanitize_for_json({"score": float("nan"), "count": np.int64(5)})
        {"score": None, "count": 5}
    """
    if obj is None:
        return None

    # Scalars: float NaN/Inf, numpy types, Decimal, UUID
    handled, result = _normalize_scalar(obj)
    if handled:
        return result

    if isinstance(obj, Enum):
        return obj.value

    # date covers datetime (subclass)
    if isinstance(obj, date):
        return obj.isoformat()

    if isinstance(obj, set | frozenset):
        return [sanitize_for_json(item) for item in obj]

    # Collections → recursive
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [sanitize_for_json(item) for item in obj]

    # Primitives (int, str, bool) → passthrough
    return obj
