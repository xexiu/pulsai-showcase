#!/usr/bin/env python3
"""Hold the turn to the ROLE: LEAD ARCHITECT / ML-AI Engineer / FINANCIAL EXPERT / Quantum Engineer.

Owner, 2026-08-06: the role is not a job title in a prompt, it is a STANDARD each turn is measured
against. Three checklist phases were repeatedly skipped, so they are enforced here rather than
merely documented in `docs/04-structural/ARCHITECT_CHECKLIST.md`:

* **PHASE 0 — DON'T REINVENT THE WHEEL.** "Junior developers create new code. Architects REUSE
  existing patterns." A new module that duplicates an existing helper/service/type is the single
  most expensive junior habit in this repo.
* **PHASE 3 — TDD, tests FIRST.** Non-negotiable. Shipping implementation with no test in the same
  turn is the failure this catches.
* **PHASE 6 — VERIFICATION COMMANDS.** ruff + mypy + pytest. "Did NOT commit with failing checks."

## What this blocks, and why each is a REAL failure mode

1. **Source written, no test written** — PHASE 3. Behaviour changed with nothing pinning it.
2. **Source written, gates never run** — PHASE 6. mypy/ruff/pytest are how "it works" stops being
   an opinion. Coverage gates are CI-blocking (BE >= 80%, FE >= 90%).
3. **A NEW module created with no reuse audit** — PHASE 0. The `reuse-check` hook already surfaces
   name-similar files; ignoring it and writing the file anyway is the violation.

Fails OPEN and self-releases after a bounded number of blocks — a guard that wedges the session
costs more than the habit it polices.
"""

from __future__ import annotations

#: Derived from the registration this guard already carries in settings.json, so
#: `register_guards --apply` can restore it if that file is ever regenerated.
HOOK_EVENT = ("PostToolUse", "Stop")
HOOK_MATCHER = "Write|Edit|NotebookEdit|Bash"

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
from _hook_state import scoped_to_session


def _session_id(payload: dict) -> str:
    """The conversation this block-bound belongs to (see `_hook_state`)."""
    return str(payload.get("session_id") or "")

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

STATE = Path(__file__).resolve().parent / ".architect_role_state.json"
_SRC = re.compile(r"\.(py|ts|tsx)$", re.IGNORECASE)
_IS_TEST = re.compile(r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]+$|\.(test|spec)\.(ts|tsx)$", re.IGNORECASE)

#: PHASE 6 — the verification commands the checklist names by hand.
_GATES = re.compile(r"(pytest|ruff|mypy|pnpm\s+(verify|type-check|lint|test)|verify\.sh)", re.IGNORECASE)


def _load(session_id: str = "") -> dict[str, Any]:
    try:
        return scoped_to_session(json.loads(STATE.read_text()), session_id)
    except Exception:
        return scoped_to_session({}, session_id)


def _save(state: dict[str, Any]) -> None:
    try:
        STATE.write_text(json.dumps(state))
    except Exception:
        pass


def classify_path(path: str) -> str | None:
    """`test` for a test file, `src` for production source, None for docs/config/anything else."""
    if not path or not _SRC.search(path):
        return None
    return "test" if _IS_TEST.search(path) else "src"


def missing_phases(state: dict[str, Any]) -> list[str]:
    """Which checklist phases this turn skipped. Empty when the turn is clean."""
    if not int(state.get("src", 0)):
        return []  # no production source touched -> nothing to enforce
    gaps: list[str] = []
    if not int(state.get("test", 0)):
        gaps.append(
            "PHASE 3 (TDD): production source was written and NO test was. Tests come FIRST — "
            "write the failing test, watch it fail, then implement."
        )
    if not int(state.get("gates", 0)):
        gaps.append(
            "PHASE 6 (VERIFICATION): source changed and ruff / mypy / pytest never ran. "
            "BE coverage >= 80% and FE >= 90% are CI-BLOCKING — a red CI is a broken promise."
        )
    return gaps


_HEADER = (
    "STOP BLOCKED — ROLE STANDARD NOT MET.\n\n"
    "You are the LEAD ARCHITECT, ML/AI Engineer, FINANCIAL EXPERT and Quantum Engineer. That is a "
    "standard this turn is measured against, not a title. "
    "`docs/04-structural/ARCHITECT_CHECKLIST.md` phases skipped:\n\n"
)

_FOOTER = (
    "\n\nAlso re-read before you stop:\n"
    "  - PHASE 0 REUSE — searched hooks / helpers / components / services / types / schemas / "
    "constants BEFORE writing anything new? \"Junior developers create new code. Architects REUSE.\"\n"
    "  - SoT + no hardcoded values, no inline types / config / components — decoupled and REUSED.\n"
    "  - SRP + SOLID, DRY without wrong abstractions (DDD_PATTERNS.md: domain = rules, "
    "infrastructure = technical, utils = no DDD).\n"
    "  - PATTERN FIT — ARCHITECTURE_PATTERNS.md: read the ANTI-FIT before adding a pattern. "
    "Golden hammer / over-abstraction / premature distribution are the named failures. A "
    "resilience pattern (retry, circuit breaker, bulkhead) with nothing emitting and nobody "
    "reading is WORSE than none: it turns a loud failure into a silent one.\n"
    "  - PERFORMANCE: polars / numpy / jit on the backend; useCallback / useMemo / memo on the "
    "frontend. Signal < 50ms, API < 200ms.\n"
    "  - Success + validation criteria stated UP FRONT, then looped until they pass."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    event = payload.get("hook_event_name") or ""
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    if event == "PostToolUse":
        state = _load(_session_id(payload))
        if tool in {"Write", "Edit", "NotebookEdit"}:
            kind = classify_path(str(tool_input.get("file_path", "")))
            if kind:
                state[kind] = int(state.get(kind, 0)) + 1
        elif tool == "Bash" and _GATES.search(str(tool_input.get("command", ""))):
            state["gates"] = int(state.get("gates", 0)) + 1
        state["updated_at"] = time.time()
        _save(state)
        return 0

    if event != "Stop":
        return 0

    state = _load(_session_id(payload))
    gaps = missing_phases(state)
    if not gaps:
        return 0

    state["blocks"] = int(state.get("blocks", 0)) + 1
    _save(state)
    reason = _HEADER + "\n".join(f"  * {g}" for g in gaps) + _FOOTER
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)  # fail OPEN — a guard must never wedge the session
