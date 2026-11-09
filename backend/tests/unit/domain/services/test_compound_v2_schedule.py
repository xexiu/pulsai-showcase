"""Behavior: compound v2 JSON schedule parsing and leg clientOrderId parsing."""

from __future__ import annotations

import pytest

from src.domain.services.compound_v2_schedule import (
    compound_v2_anchor_short_hash_from_paper_order_id,
    normalize_compound_leg_schedule_v2,
    try_parse_compound_v2_leg_client_order_id,
)
from src.shared.exceptions import ValidationError


def _leg_client_order_id(anchor: str, leg: int) -> str:
    return f"pa2l-{compound_v2_anchor_short_hash_from_paper_order_id(anchor)}-{leg:02d}"


def test_normalize_empty_and_rows() -> None:
    assert normalize_compound_leg_schedule_v2(None) == []
    assert normalize_compound_leg_schedule_v2([{"leverage": 2}, {"leverage": 5}]) == [
        {"leverage": 2},
        {"leverage": 5},
    ]


def test_normalize_rejects_bad_shape() -> None:
    with pytest.raises(ValidationError):
        normalize_compound_leg_schedule_v2("nope")
    with pytest.raises(ValidationError):
        normalize_compound_leg_schedule_v2([{"leverage": 0}])


class TestCompoundV2LegClientOrderIdParse:
    def test_parse_roundtrips_leg_id(self) -> None:
        anchor = "550e8400-e29b-41d4-a716-446655440000"
        for leg in (0, 1, 98):
            built = _leg_client_order_id(anchor, leg)
            parsed = try_parse_compound_v2_leg_client_order_id(built)
            assert parsed is not None
            h20, idx = parsed
            assert idx == leg
            assert h20 == compound_v2_anchor_short_hash_from_paper_order_id(anchor)

    def test_parse_rejects_uppercase_hex(self) -> None:
        anchor = "550e8400-e29b-41d4-a716-446655440000"
        built = _leg_client_order_id(anchor, 1)
        h = built.split("-")[1]
        if not any(c in "abcdef" for c in h):
            pytest.skip("anchor hash prefix is digit-only for this UUID")
        first_lower = next(c for c in h if c in "abcdef")
        mangled = built.replace(first_lower, first_lower.upper(), 1)
        assert mangled != built
        assert try_parse_compound_v2_leg_client_order_id(mangled) is None

    def test_parse_rejects_bad_shape(self) -> None:
        assert try_parse_compound_v2_leg_client_order_id(None) is None
        assert try_parse_compound_v2_leg_client_order_id("") is None
        assert try_parse_compound_v2_leg_client_order_id("pa2l-short-01") is None
        assert try_parse_compound_v2_leg_client_order_id("pam-abc-01") is None
        assert try_parse_compound_v2_leg_client_order_id("pa2l-gg-01") is None

    def test_parse_rejects_leg_index_over_cap(self) -> None:
        assert try_parse_compound_v2_leg_client_order_id("pa2l-00000000000000000000-99") is None
