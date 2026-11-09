"""
Coerce Python Enum members or primitives to plain strings for API / JSON.

WHY this module exists:
- Pydantic ``field_validator(..., mode="before")`` receives ``object``; Pyright
  rejects ``value.value`` without a narrow type.
- SQLAlchemy may hand us a Python ``Enum`` member or a raw string depending on
  dialect / loader — one explicit coercion keeps validators DRY and explicit.

@see docs/04-structural/CODING_STANDARDS.md — explicit control flow, no magic.
"""

from enum import Enum


def coerce_enum_like_to_str(value: object) -> str:
    """
    Normalize ORM / validation input to a string for JSON responses.

    Args:
        value: Enum member (e.g. ``RegistrationSource``), ``str``, or other.

    Returns:
        String form suitable for API clients (enum ``.value`` when applicable).
    """
    if isinstance(value, Enum):
        inner = value.value
        if isinstance(inner, str):
            return inner
        return str(inner)
    if isinstance(value, str):
        return value
    return str(value)
