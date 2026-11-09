#!/usr/bin/env python3
"""The one way a PreToolUse guard refuses a tool call.

IMPORTERS/CALLERS: documentation_room_guard.py, one_definition_guard.py (GATE-TRANSCRIPTS 2/n); the 43 other hooks that
print the same object by hand move here in GATE-TRANSCRIPTS 3/n; test__hook_deny.py. AFFECTED API: none.
DATA SCHEMAS: stdout carries Claude Code's PreToolUse decision object -- {"hookSpecificOutput": {"hookEventName":
"PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": <reason>}} -- which _hook_mode_gate.DECISIVE
also reads; the reason is echoed on stderr for the transcript view.

WHY (GATE-TRANSCRIPTS, 2026-11-07): MEASURED -- 44 non-test hooks build this object by hand, 17 of them also echoing
the reason on stderr and 27 not. `.claude/hooks` sits outside every DRY gate, so nothing saw the copies.
"""

from __future__ import annotations

import json
import sys


def print_tool_denial(reason: str) -> None:
    """Refuse the pending tool call with ``reason``: the decision object on stdout, the reason on stderr."""
    decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}
    print(json.dumps({"hookSpecificOutput": decision}))
    print(reason, file=sys.stderr)
