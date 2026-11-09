"""Backward-compatible re-export. Source of truth: ``src.shared.utils.serialization``."""

from __future__ import annotations

from src.shared.utils.serialization import (
    dataclass_to_dict,
    load_json_str_list,
    round_finite,
    sanitize_for_json,
    sanitize_scalar_for_json,
)

__all__ = [
    "dataclass_to_dict",
    "load_json_str_list",
    "round_finite",
    "sanitize_for_json",
    "sanitize_scalar_for_json",
]
