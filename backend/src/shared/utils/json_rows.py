"""The JSON objects of a decoded JSON list -- ONE home for the "list of dicts, anything else is no rows" coercion --
and of a JSON-lines file (jsonl_rows, 2026-10-17: expression_clones listed `[json.loads(line) for line in
path.read_text().splitlines() if line.strip()]` in 4 functions with no src/shared home).

json_object (2026-10-18): one decoded JSON value as a typed object or None -- the gates' basedpyright / cache readers
narrowed json.loads with isinstance(x, dict), which no checker can type (dict[Unknown, Unknown]).

IMPORTERS/CALLERS: src/research/engine/runtime/leadlag_engine (the demo host's contract list), engine_exec_report
(jsonl_rows: the engines' ledgers), lighter_rest, mexc_rest, engine_charts (dict_rows); quality_gates.expression_clones
and verify_gate_helpers (json_object); tests/unit/shared/utils/test_json_rows.py. AFFECTED API: json_object added.
DATA SCHEMAS: none.

REUSE-AUDIT: expression_clones listed this exact expression in 6 functions with no src/shared home
(bulkowski_pattern_alert_dispatch.persist_open_fire, mexc_rest.open_positions, all_tf_exit_confidence_walkforward.
load_gate_rows, coinglass_derivatives_ic._load_previous_results, edge_hunt/registry_leaf.as_rows, leadlag_engine._rows);
src/shared/utils held enum / timestamp / feature-importance JSON helpers only. The remaining five sites call this when
their files are next touched: rewiring them now was measured to owe ~15 unrelated touched-debt reductions (29 Any
references, a global, two >100-line functions, blind excepts) for a one-line change (2026-10-13).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path


def json_object(value: object) -> dict[str, object] | None:
    """``value`` when it is a JSON object (a dict: JSON object keys are always strings), else None."""
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def dict_rows(value: object) -> list[dict[str, object]]:
    """The dict elements of ``value`` when it is a list; anything else (None, a dict, a number) yields no rows."""
    items = cast("list[object]", value) if isinstance(value, list) else []
    return [row for item in items if (row := json_object(item)) is not None]


def jsonl_rows(path: Path) -> list[dict[str, object]]:
    """The JSON objects of a JSON-lines file (a ledger, a tape), one per line, blank lines skipped; a line that decodes
    to something other than an object is not a row."""
    return dict_rows([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])  # CLONE-OK: the home
