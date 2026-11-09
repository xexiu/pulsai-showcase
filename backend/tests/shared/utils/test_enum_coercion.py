"""Behavior tests for enum → API string coercion."""

from enum import Enum

import pytest

from src.domain.enums import RegistrationSource
from src.shared.utils.enum_coercion import coerce_enum_like_to_str


class _IntEnum(Enum):
    A = 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (RegistrationSource.DIRECT, "direct"),
        ("direct", "direct"),
        (42, "42"),
    ],
)
def test_coerce_enum_like_to_str(raw: object, expected: str) -> None:
    assert coerce_enum_like_to_str(raw) == expected


def test_coerce_non_str_enum_value() -> None:
    assert coerce_enum_like_to_str(_IntEnum.A) == "1"
