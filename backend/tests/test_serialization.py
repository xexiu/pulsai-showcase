"""
Tests for JSON sanitization utility.

TDD: Tests written FIRST before implementation (per .cursorrules).

Tests BEHAVIOR:
- Does it make NaN/Inf/numpy types JSON-safe?
- Does it recursively handle nested structures?
- Does it leave normal values unchanged?
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import UUID

import numpy as np
import pytest

from src.utils.serialization import (
    load_json_str_list,
    round_finite,
    sanitize_for_json,
    sanitize_scalar_for_json,
)


class TestSanitizeForJsonScalars:
    """Test individual value sanitization."""

    def test_nan_becomes_none(self) -> None:
        """float('nan') -> None (NaN is invalid in JSON per RFC 8259)."""
        assert sanitize_for_json(float("nan")) is None

    def test_inf_becomes_none(self) -> None:
        """float('inf') -> None (Infinity is invalid in JSON per RFC 8259)."""
        assert sanitize_for_json(float("inf")) is None

    def test_negative_inf_becomes_none(self) -> None:
        """float('-inf') -> None."""
        assert sanitize_for_json(float("-inf")) is None

    def test_np_float64_becomes_python_float(self) -> None:
        """np.float64(3.14) -> float(3.14) (JSON-serializable)."""
        result = sanitize_for_json(np.float64(3.14))
        assert isinstance(result, float)
        assert result == pytest.approx(3.14)

    def test_np_int64_becomes_python_int(self) -> None:
        """np.int64(42) -> int(42)."""
        result = sanitize_for_json(np.int64(42))
        assert isinstance(result, int)
        assert result == 42

    def test_np_int32_becomes_python_int(self) -> None:
        """np.int32(7) -> int(7)."""
        result = sanitize_for_json(np.int32(7))
        assert isinstance(result, int)
        assert result == 7

    def test_np_bool_true_becomes_python_bool(self) -> None:
        """np.bool_(True) -> bool(True)."""
        result = sanitize_for_json(np.bool_(True))
        assert isinstance(result, bool)
        assert result is True

    def test_np_bool_false_becomes_python_bool(self) -> None:
        """np.bool_(False) -> bool(False)."""
        result = sanitize_for_json(np.bool_(False))
        assert isinstance(result, bool)
        assert result is False

    def test_np_float64_nan_becomes_none(self) -> None:
        """np.float64('nan') -> None."""
        assert sanitize_for_json(np.float64("nan")) is None

    def test_np_float64_inf_becomes_none(self) -> None:
        """np.float64('inf') -> None."""
        assert sanitize_for_json(np.float64("inf")) is None

    def test_decimal_becomes_str(self) -> None:
        """Decimal -> str (JSON + SQLAlchemy JSON columns have no default=)."""
        assert sanitize_for_json(Decimal("0.5")) == "0.5"

    def test_uuid_becomes_str(self) -> None:
        u = UUID("11111111-1111-1111-1111-111111111111")
        assert sanitize_for_json(u) == "11111111-1111-1111-1111-111111111111"


class TestSanitizeScalarForJson:
    """Direct scalar sanitizer for call sites that only normalize one JSON value."""

    def test_nan_becomes_none(self) -> None:
        assert sanitize_scalar_for_json(float("nan")) is None

    def test_inf_becomes_none(self) -> None:
        assert sanitize_scalar_for_json(float("inf")) is None

    def test_finite_float_passes_through(self) -> None:
        result = sanitize_scalar_for_json(3.14)
        assert isinstance(result, float)
        assert result == pytest.approx(3.14)

    def test_bool_passes_through(self) -> None:
        assert sanitize_scalar_for_json(True) is True


class TestRoundFinite:
    """JSON dump helper: round a measurable float; NaN/Inf are unknown, not zero."""

    def test_rounds_a_finite_value(self) -> None:
        assert round_finite(1.23456, 4) == 1.2346

    def test_nan_is_none_not_zero(self) -> None:
        """0.0 would read as 'measured, no relationship' — the serialization SoT uses None."""
        assert round_finite(float("nan"), 4) is None

    def test_inf_is_none(self) -> None:
        assert round_finite(float("inf"), 2) is None
        assert round_finite(float("-inf"), 2) is None

    def test_numpy_nan_is_none(self) -> None:
        assert round_finite(float(np.float64("nan")), 4) is None


class TestLoadJsonStrList:
    """One door for frozen feature_names / sibling JSON string-list artifacts."""

    def test_reads_named_key(self, tmp_path: Path) -> None:
        path = tmp_path / "features.json"
        path.write_text('{"feature_names": ["atr_14", "bb_width"], "n_features": 2}', encoding="utf-8")
        assert load_json_str_list(path, "feature_names") == ["atr_14", "bb_width"]

    def test_missing_required_file_raises_with_hint(self, tmp_path: Path) -> None:
        path = tmp_path / "features.json"
        with pytest.raises(FileNotFoundError, match="materialize_nonprice"):
            load_json_str_list(
                path,
                "feature_names",
                missing_hint="run materialize_nonprice_inference_artifacts.py before the SA validate script",
            )

    def test_optional_missing_file_is_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "features.json"
        assert load_json_str_list(path, "feature_names", required=False) == []

    def test_optional_missing_key_is_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "features.json"
        path.write_text("{}", encoding="utf-8")
        assert load_json_str_list(path, "feature_names", required=False) == []

    def test_required_missing_key_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "features.json"
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(KeyError, match="feature_names"):
            load_json_str_list(path, "feature_names")


class _SampleEnum(Enum):
    X = "x"


class TestSanitizeForJsonPassthrough:
    """Test that normal values pass through unchanged."""

    def test_none_passes_through(self) -> None:
        assert sanitize_for_json(None) is None

    def test_int_passes_through(self) -> None:
        assert sanitize_for_json(42) == 42

    def test_float_passes_through(self) -> None:
        assert sanitize_for_json(3.14) == pytest.approx(3.14)

    def test_string_passes_through(self) -> None:
        assert sanitize_for_json("hello") == "hello"

    def test_bool_passes_through(self) -> None:
        assert sanitize_for_json(True) is True

    def test_enum_becomes_value(self) -> None:
        assert sanitize_for_json(_SampleEnum.X) == "x"

    def test_date_isoformat(self) -> None:
        assert sanitize_for_json(date(2026, 4, 18)) == "2026-04-18"

    def test_datetime_isoformat(self) -> None:
        dt = datetime(2026, 4, 18, 12, 30, 0, tzinfo=UTC)
        assert sanitize_for_json(dt) == "2026-04-18T12:30:00+00:00"


class TestSanitizeForJsonNested:
    """Test recursive sanitization of nested structures."""

    def test_dict_with_nan_values(self) -> None:
        """Nested dict with NaN values -> recursively sanitized."""
        data = {"score": float("nan"), "name": "test", "value": 42}
        result = sanitize_for_json(data)

        assert result == {"score": None, "name": "test", "value": 42}

    def test_list_with_inf(self) -> None:
        """List containing Inf -> recursively sanitized."""
        data = [1.0, float("inf"), 3.0, float("-inf")]
        result = sanitize_for_json(data)

        assert result == [1.0, None, 3.0, None]

    def test_deeply_nested_structure(self) -> None:
        """Deeply nested dicts and lists are recursively sanitized."""
        data = {
            "metrics": {
                "sharpe": float("nan"),
                "returns": [0.1, float("inf"), -0.2],
            },
            "count": np.int64(100),
            "valid": np.bool_(True),
        }
        result = sanitize_for_json(data)

        assert result["metrics"]["sharpe"] is None
        assert result["metrics"]["returns"] == [0.1, None, -0.2]
        assert result["count"] == 100
        assert isinstance(result["count"], int)
        assert result["valid"] is True
        assert isinstance(result["valid"], bool)

    def test_tuple_converted_to_list(self) -> None:
        """Tuples are sanitized like lists."""
        data = (1.0, float("nan"), 3.0)
        result = sanitize_for_json(data)
        assert result == [1.0, None, 3.0]

    def test_empty_dict(self) -> None:
        assert sanitize_for_json({}) == {}

    def test_empty_list(self) -> None:
        assert sanitize_for_json([]) == []


class TestSanitizeForJsonIntegration:
    """Integration: sanitized output produces valid JSON."""

    def test_sanitized_data_produces_valid_json(self) -> None:
        """sanitize_for_json() output can be serialized with json.dumps()."""
        data = {
            "nan_val": float("nan"),
            "inf_val": float("inf"),
            "neg_inf": float("-inf"),
            "np_float": np.float64(3.14),
            "np_int": np.int64(42),
            "np_bool": np.bool_(True),
            "nested": {"inner_nan": float("nan"), "scores": [1.0, float("inf")]},
            "normal": "test",
        }
        sanitized = sanitize_for_json(data)

        # This MUST NOT raise -- valid JSON
        json_str = json.dumps(sanitized)

        # Parse it back to verify roundtrip
        parsed = json.loads(json_str)
        assert parsed["nan_val"] is None
        assert parsed["inf_val"] is None
        assert parsed["neg_inf"] is None
        assert parsed["np_float"] == pytest.approx(3.14)
        assert parsed["np_int"] == 42
        assert parsed["np_bool"] is True
        assert parsed["nested"]["inner_nan"] is None
        assert parsed["nested"]["scores"] == [1.0, None]

    def test_audit_like_payload_is_json_serializable(self) -> None:
        """Mirrors paper_order_placed audit details (Pydantic Decimals, etc.)."""
        payload = {
            "symbol": "BTC/USDT",
            "min_compound_step_pct": Decimal("0.5"),
            "nested": {"id": UUID("22222222-2222-2222-2222-222222222222")},
        }
        sanitized = sanitize_for_json(payload)
        json.dumps(sanitized)
        assert sanitized["min_compound_step_pct"] == "0.5"
        assert sanitized["nested"]["id"] == "22222222-2222-2222-2222-222222222222"

    def test_raw_nan_produces_invalid_json(self) -> None:
        """Demonstrate the bug: json.dumps(float('nan')) produces invalid JSON."""
        # This is the bug we're fixing -- json.dumps doesn't reject NaN
        raw = json.dumps(float("nan"))
        # Python's json.dumps produces "NaN" which is NOT valid JSON
        assert raw == "NaN"

        # json.loads rejects it when strict=True... actually Python accepts it
        # but other JSON parsers (JavaScript, Go, Rust) would reject it
