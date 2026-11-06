"""json_object: a decoded JSON value when it is an object, None for anything else; dict_rows: the dict elements of a
decoded JSON list, no rows for anything else; jsonl_rows: a JSON-lines file's objects, blank lines skipped.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.shared.utils.json_rows import dict_rows, json_object, jsonl_rows

if TYPE_CHECKING:
    from pathlib import Path


def test_a_jsonl_file_reads_one_object_per_line_and_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"trade": 1}\n\n  \n{"trade": 2, "event": "open"}\n', encoding="utf-8")
    assert jsonl_rows(path) == [{"trade": 1}, {"trade": 2, "event": "open"}]


def test_a_list_keeps_only_its_dict_elements() -> None:
    assert dict_rows([{"a": 1}, 2, "x", None, {"b": 2}]) == [{"a": 1}, {"b": 2}]


def test_anything_that_is_not_a_list_yields_no_rows() -> None:
    assert dict_rows({"a": 1}) == []
    assert dict_rows(None) == []
    assert dict_rows("[]") == []


def test_a_json_object_is_returned_as_it_is() -> None:
    value = {"summary": {"errorCount": 0}}
    assert json_object(value) is value


def test_anything_that_is_not_a_json_object_is_none() -> None:
    assert json_object([{"a": 1}]) is None
    assert json_object(None) is None
    assert json_object("{}") is None
    assert json_object(3) is None
