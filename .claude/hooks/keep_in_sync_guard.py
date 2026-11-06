#!/usr/bin/env python3
"""PreToolUse(Write|Edit): a COMMENT is not a synchronisation mechanism.

Owner, 2026-08-14:

    "Give someone state and they'll have a bug one day, but teach them how to represent state in
     two separate locations that have to be kept in sync and they'll have bugs for a lifetime."

Duplicated state is not one bug, it is a BUG GENERATOR: every copy is a place someone edits alone,
and every future change is a fresh chance to diverge. "Keep in sync" delegates that to human
memory forever.

MEASURED 2026-08-14 — 8 live promises of this shape in the repo, each guarded only by prose:

    src/application/services/prod_xs_fifo_features.py   "Match edge_lab.feature_sources... (keep in sync)"
    src/shared/constants/contact_inquiry.py             "keep in sync with web contact i18n / Valibot enum"
    web/src/utils/constants/regimeTaxonomy.ts           "Regime taxonomy mirror (FE) — keep in sync with"
    web/src/utils/modelId.ts                            "keep in sync with the backend parser"
    web/src/styles/globals.css                          "keep in sync with PLOTLY_EQUITY_CURVE_LINE_*"
    ... and 3 more

What one of them cost (memory `a-mirror-needs-a-mechanism`): `2h`/`6h` went missing from the TS
timeframe mirror and were filed under CHART_ONLY, telling the frontend that two real trading
timeframes were decoration, while a sibling validator had drifted SEVEN timeframes behind and
rejected `30m`, `8h`, `12h`, `3d`, `1w` outright. Nothing failed; it just silently disagreed.

RELEASES on a named mechanism — a parity/contract test, or a statement that the value is DERIVED
(no second copy at all, the better fix). Judges only ADDED text, so it never punishes touching a
file that already carries an old promise. Fails OPEN on any internal error.
"""

from __future__ import annotations

import json
import re
import sys

HOOK_EVENT = "PreToolUse"
HOOK_MATCHER = "Edit|Write"

#: The promise: two copies that a human must remember to reconcile.
_PROMISE = re.compile(
    r"(keep(?:ing|s)?\s+(?:\w+\s+){0,3}in\s+sync|kept\s+in\s+sync|stay\s+in\s+sync"
    r"|must\s+match\s+the\b|mirror\s+of\b|\bmirror\s*\(|\bmirror\b[^\n]{0,40}\bkeep)",
    re.IGNORECASE,
)

#: An executable check, or the absence of a second copy. Either discharges the promise.
_MECHANISM = re.compile(
    r"(parity[_\s-]?test|test_\w*parity|contract[_\s-]?test|\bderived\b|\bderive[sd]?\s+from\b"
    r"|fails?\s+on\s+disagreement|reads?\s+the\s+other\s+file|no\s+second\s+copy"
    r"|pinned\s+by\s+(?:a\s+)?test|asserts?\s+.{0,30}\bmatch(?:es)?\b"
    # Reusing / importing the existing definition IS mechanism 1: there is no second location
    # left to reconcile. FALSE POSITIVE 2026-08-14 — this guard blocked its own author writing
    # "Reuses the existing constant rather than restating 95.0", i.e. doing exactly the right
    # thing while naming the anti-pattern it was avoiding. A guard that blocks the correct fix
    # teaches people to route around it, which is worse than not having the guard.
    r"|reus(?:e|es|ing)\s+the\s+(?:existing|shared)\b"
    r"|imports?\s+the\s+(?:existing|shared)\b"
    r"|single\s+source\s+of\s+truth)",
    re.IGNORECASE,
)


def promises_sync_without_mechanism(added_text: str) -> bool:
    """True when ADDED text promises to keep copies in sync and names no way to enforce it."""
    if not added_text or not added_text.strip():
        return False
    if not _PROMISE.search(added_text):
        return False
    return not _MECHANISM.search(added_text)


def _added_text(tool_input: dict) -> str:
    """The text this edit INTRODUCES — never the whole file, so old promises are not re-judged."""
    if "content" in tool_input:  # Write
        return str(tool_input.get("content") or "")
    parts = [str(tool_input.get("new_string") or "")]  # Edit
    for edit in tool_input.get("edits") or []:  # MultiEdit
        if isinstance(edit, dict):
            parts.append(str(edit.get("new_string") or ""))
    return "\n".join(parts)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail open — a guard must never wedge the session

    try:
        tool_input = payload.get("tool_input") or {}
        path = str(tool_input.get("file_path") or "")
        # The guard's own tests and this file quote the banned phrases on purpose.
        if "keep_in_sync_guard" in path:
            return 0
        if not promises_sync_without_mechanism(_added_text(tool_input)):
            return 0
    except Exception:
        return 0

    print(
        "BLOCKED — this edit promises to keep two copies in sync, and names no mechanism.\n"
        "\n"
        '  "Give someone state and they\'ll have a bug one day, but teach them how to represent\n'
        '   state in two separate locations that have to be kept in sync and they\'ll have bugs\n'
        '   for a lifetime."  — owner, 2026-08-14\n'
        "\n"
        "Duplicated state is a BUG GENERATOR, not a bug: each copy is a place someone edits alone.\n"
        "MEASURED: 8 live `keep in sync` comments in this repo. One of them let `2h`/`6h` vanish\n"
        "from the TS timeframe mirror (filed under CHART_ONLY — real trading timeframes described\n"
        "to the FE as decoration) while a sibling validator drifted 7 timeframes behind. Nothing\n"
        "failed; it silently disagreed.\n"
        "\n"
        "Do one:\n"
        "  1. DERIVE it — remove the second location so there is nothing to reconcile (best); or\n"
        "  2. name the PARITY TEST that reads the other file and FAILS on disagreement; or\n"
        "  3. if the copy is unavoidable and already pinned, say so and cite the test.\n"
        "\n"
        "Guard the guard: a parity test that SKIPS when it cannot find its counterpart is a guard\n"
        "that silently does not exist — assert the other file is present before comparing.\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
