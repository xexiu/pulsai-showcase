"""P8-L-3 (G-6 remediation): SoT-JSON contract parity for ``compound_leg_schedule_v2``.

The ``compound_leg_schedule_v2`` payload is internal-only today (strategy
snapshots feed it in; see ``_INTERNAL_ONLY_HTTP_FIELDS``). It is, however,
the highest-leverage payload in the unified trading path — one mistyped
``leverage`` row silently drops to anchor leverage, producing a position
sized for an entirely different risk profile.

This module pins the contract shape in a single committed JSON document
(:file:`contracts/compound_leg_schedule_v2.contract.json`) and asserts that
:func:`normalize_compound_leg_schedule_v2` honors it. When a future FE
strategy editor starts emitting this payload, a Valibot parity test can
read the same JSON to lock both ends in place. Until then, this test
alone prevents silent BE drift.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.helpers.api_paths import REPO_ROOT


def _load_contract() -> dict[str, Any]:
    repo_root = REPO_ROOT
    contract_path = repo_root / "contracts" / "compound_leg_schedule_v2.contract.json"
    assert contract_path.is_file(), f"Contract SOT not found at {contract_path}"
    return json.loads(contract_path.read_text(encoding="utf-8"))


class TestContractDocumentShape:
    def test_required_top_level_keys_present(self) -> None:
        contract = _load_contract()
        for key in ("description", "backend_validator", "row_schema"):
            assert key in contract, f"contract missing top-level key {key!r}"

    def test_backend_validator_points_at_normalize_function(self) -> None:
        contract = _load_contract()
        assert contract["backend_validator"].endswith(
            "compound_v2_schedule.py::normalize_compound_leg_schedule_v2",
        )

    def test_row_schema_requires_leverage_int_ge_1(self) -> None:
        contract = _load_contract()
        row = contract["row_schema"]
        assert row["required_fields"] == ["leverage"]
        lev = row["fields"]["leverage"]
        assert lev["type"] == "integer"
        assert lev["minimum"] == 1


class TestNormalizeHonorsContract:
    def test_required_field_from_contract_is_enforced(self) -> None:
        """Every ``required_fields`` entry on the contract must fail validation when missing."""
        from src.domain.services.compound_v2_schedule import (
            normalize_compound_leg_schedule_v2,
        )
        from src.shared.exceptions import ValidationError

        contract = _load_contract()
        required = list(contract["row_schema"]["required_fields"])
        assert required, "contract row_schema.required_fields must not be empty"

        for missing_key in required:
            row: dict[str, Any] = dict.fromkeys(required, 1)
            row.pop(missing_key)
            with pytest.raises(ValidationError):
                normalize_compound_leg_schedule_v2([row])

    def test_leverage_minimum_from_contract_is_enforced(self) -> None:
        from src.domain.services.compound_v2_schedule import (
            normalize_compound_leg_schedule_v2,
        )
        from src.shared.exceptions import ValidationError

        contract = _load_contract()
        minimum = int(contract["row_schema"]["fields"]["leverage"]["minimum"])

        with pytest.raises(ValidationError):
            normalize_compound_leg_schedule_v2([{"leverage": minimum - 1}])

        result = normalize_compound_leg_schedule_v2([{"leverage": minimum}])
        assert result == [{"leverage": minimum}]

    def test_non_list_payload_rejected(self) -> None:
        from src.domain.services.compound_v2_schedule import (
            normalize_compound_leg_schedule_v2,
        )
        from src.shared.exceptions import ValidationError

        with pytest.raises(ValidationError):
            normalize_compound_leg_schedule_v2({"leverage": 5})

    def test_non_object_row_rejected(self) -> None:
        from src.domain.services.compound_v2_schedule import (
            normalize_compound_leg_schedule_v2,
        )
        from src.shared.exceptions import ValidationError

        with pytest.raises(ValidationError):
            normalize_compound_leg_schedule_v2([42])

    def test_none_payload_returns_empty_list(self) -> None:
        """Contract notes ``null`` is the explicit "no schedule" signal."""
        from src.domain.services.compound_v2_schedule import (
            normalize_compound_leg_schedule_v2,
        )

        contract = _load_contract()
        assert contract["null_payload_policy"] == "normalize_to_empty_list"
        assert normalize_compound_leg_schedule_v2(None) == []


class TestContractVsImplementationFieldSet:
    def test_contract_only_declares_fields_the_normalizer_actually_reads(self) -> None:
        """Fields listed on the contract MUST be the fields the BE normalizer honors today.

        The BE normalizer reads exactly ``leverage`` from each row. If a future
        contract update adds e.g. ``entry_pct_offset`` without wiring the
        normalizer, this assertion must flip first.
        """
        from src.domain.services.compound_v2_schedule import (
            normalize_compound_leg_schedule_v2,
        )

        contract = _load_contract()
        declared_fields = set(contract["row_schema"]["fields"].keys())

        # Execute the normalizer with every declared field set to a sentinel
        # int value and check every declared field survives to the output OR
        # the contract marks it as advisory.
        row = dict.fromkeys(declared_fields, 2)
        (out,) = normalize_compound_leg_schedule_v2([row])

        advisory: set[str] = set(contract["row_schema"].get("advisory_fields", []))
        honored_fields = declared_fields - advisory

        for field in honored_fields:
            assert field in out, (
                f"Contract declares {field!r} as honored but normalizer dropped it. "
                "Either wire the field through or mark it advisory in the contract."
            )
