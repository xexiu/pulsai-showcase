#!/usr/bin/env python3
"""Block gate/threshold edits that were NOT preceded by an empirical check.

THE FAILURE THIS EXISTS FOR (owner fury, 2026-08-05, "again, your updating gates WITHOUT
THINKING!!"): a promotion gate was added to `capital_cert_promote.py` on instinct — it read as
rigorous, it passed 139 tests, ruff and mypy were clean. Deep investigation afterwards showed it was
a NO-OP on 27 of 28 real certs (they record `window_is_in_sample = None`, which the gate lets
through), while the defect that actually cost money sat elsewhere entirely: the cert headline was
selected from a 25-cell search path and never looked at the 3,840-cell grid in the SAME artifact —
which contained liquidation-clean cells beating buy-and-hold by 5x.

A gate that compiles, tests green and lints clean can still be the wrong gate. Tests prove the code
does what it says; only DATA proves it was worth saying. So: before changing a gate, threshold,
eligibility rule or promotion condition, RUN THE CORPUS and see the wrong number with your own eyes.

Enforcement is two-sided and shares one state file:
  * PostToolUse(Bash)  -> record a verification event when the command actually reads real data.
  * PreToolUse(Edit|Write) -> on a gate-ish target, DENY unless such an event is recent.

Fails OPEN on any internal error: a broken guard must never wedge the session.
"""

from __future__ import annotations

#: Derived from the registration this guard already carries in settings.json, so
#: `register_guards --apply` can restore it if that file is ever regenerated.
HOOK_EVENT = ("PostToolUse", "PreToolUse")

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

#: Overridable so a SUBPROCESS-spawned hook can be tested against isolated state. Patching the
#: module attribute only reaches in-process callers; the subprocess re-reads this at import.
STATE = Path(os.environ.get("INVESTIGATE_GUARD_STATE", Path(__file__).resolve().parent / ".investigate_state.json"))

#: How much of the licensing command to keep. Enough to recognise WHICH investigation it was;
#: short enough that a pasted heredoc cannot bloat the state file the guard reads on every edit.
_LICENCE_EXCERPT_CHARS = 240

# How long an empirical check "covers" subsequent gate edits. Long enough to investigate then edit
# in one flow; short enough that a check from earlier unrelated work does not license a blind edit.
#
# PROVENANCE: 30 -> 60 minutes, owner call 2026-08-15, after watching a real gate edit sail through
# on a corpus read that had nothing to do with the number being changed. His words: "why 30 min??
# why that magic number? who made that? should be 1h min".
#
# AND THE WINDOW WAS NEVER THE WEAK PART. Recency was all this recorded — a `jq` on any artifact
# licensed any gate edit, because the state file held a bare timestamp and nothing else. So the
# guard could answer "did you look at data?" and never "did you look at THIS data". The command
# text is now stored and shown, which makes an irrelevant licence visible instead of silent.
# Lengthening the window is only safe BECAUSE of that: a longer licence with no audit trail would
# have been strictly worse.
WINDOW_SECONDS = 60 * 60

# Path signals that a file encodes a DECISION RULE rather than mechanism.
_GATE_PATH = re.compile(
    r"(promote|eligib|gate|threshold|policy|verdict|cert_|_cert|headline|survivor)",
    re.IGNORECASE,
)

# Source files that can hold a decision rule. A gate is not a Python idea: PulsAI ships tier
# thresholds, visibility rules and eligibility checks in `apps/web` config and hooks too, and
# this guard used to `return False` on anything not ending in `.py` -- so every one of them
# could be edited with no empirical check at all.
_SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

# Content signals that the edit introduces/moves a decision boundary.
#
# `return\s+False` is CAPITALISED -- Python only. TypeScript writes `return false`, so even
# after the suffix fix above, an FE gate would have slipped through on content. Both spellings
# now count, plus the strict-equality operators TS actually uses.
_GATE_CONTENT = re.compile(
    r"(return\s+(?:False|True|false|true)\b"
    r"|>=|<=|!==|===|[^=!<>]==[^=]"
    r"|MIN_|MAX_|_FLOOR|_THRESHOLD|_CUTOFF)",
)

# A Bash command that genuinely interrogates real data (not `ls`, not `git status`).
_VERIFY_CMD = re.compile(
    r"(json\.load|read_parquet|read_csv|pd\.read|pl\.read|SELECT\s|psql|sqlite3"
    r"|\.json['\"\s)]|artifacts/|capital_cert|combo_top|dca_cells|pytest|curl\s"
    # FE ways of actually looking at the data behind a rule. Without these, doing the
    # legwork with `jq`, a vitest run or a node script counted as having checked NOTHING,
    # and the guard would deny a well-researched frontend gate edit.
    r"|\bjq\b|vitest|pnpm\s+test|node\s+-e|npx\s+tsx|\.csv['\"\s)]|\.parquet['\"\s)])",
    re.IGNORECASE,
)


# A NEW numeric policy constant, e.g. `MAX_DD_FLOOR = -0.40` or `MIN_SHARPE = 1.5`.
#
# THE GAP THIS CLOSES (owner, 2026-08-10: "who decided that magic number and why?"). The guard
# above asks whether DATA was read before a gate edit. It never asks whether the NUMBER was
# justified. Both questions have to be answered, and only the first was: `MAX_DD_FLOOR = -0.40`
# was copied into the domain layer from a research helper, with corpus reads happening in the
# same window — so the guard passed it. Asked for the provenance, there was none to give.
#
# The value turned out to be the wrong SHAPE, not merely the wrong number: the published CTA
# standard is drawdown relative to annualised return (Calmar >= 2), not an absolute cap. A fixed
# -0.40 admitted 7 of 8 candidate books; the return-relative rule admits 2.
_MAGIC_THRESHOLD = re.compile(
    r"^\s*(?!#)[A-Z][A-Z0-9_]*(?:_FLOOR|_THRESHOLD|_CUTOFF|_MIN|_MAX|_LIMIT)\s*[:=]"
    r"[^=\n]*?(-?\d+\.?\d*)",
    re.MULTILINE,
)

# Evidence that the author justified the value rather than inheriting it. A URL or an explicit
# PROVENANCE/measured note is cheap to write and is exactly what was missing.
_PROVENANCE = re.compile(
    r"(PROVENANCE:|https?://|\bmeasured\b|\bcited\b|\bper\s+\w+\s+standard\b|\bderived from\b)",
    re.IGNORECASE,
)


#: A re-edit of a decision site ALREADY changed in this window must say what refuted the last one.
#:
#: THE GAP (owner, 2026-08-14, after eight days): *"tomorrow you will say use this logic and that
#: logic and output will be different than yesterday and you will change your mind"*. The two
#: checks above ask whether DATA was read and whether a NUMBER was justified. Neither notices the
#: same rule being decided a third time.
#:
#: Measured on the session that produced this: the SELECT rule was rewritten THREE times in one
#: turn — exclude all-in, then rank by MAR, then apply the risk floor — and every rewrite passed
#: this guard, because each had corpus reads in its window and reused an existing constant.
#:
#: Those three were LEGITIMATE, and that is the whole design constraint: each one cited the
#: measurement that REFUTED its predecessor (all-in exclusion still froze -75% losers; MAR picks
#: $10,030 on $10,000). Blocking iteration would have blocked the work that fixed the defect.
#: Drift is a re-decision with no refutation attached — so that, and only that, is what this asks
#: for. The evidence is already being written when the change is real.
_REFUTATION = re.compile(
    r"(refut\w*|MEASURED\b|measured (?:on|across|that)|superseded|did not hold|turned out"
    r"|was wrong|proved wrong|contradict\w*|the data says|counted)",
    re.IGNORECASE,
)


def redecides_without_refutation(
    path: str, new_text: str, state: dict[str, Any], *, now: float
) -> bool:
    """True when this decision site was already changed in the window and nothing refutes it."""
    if not is_gate_edit(path, new_text):
        return False
    previous = (state.get("gate_edits") or {}).get(path)
    if previous is None or (now - float(previous)) > WINDOW_SECONDS:
        return False
    return not _REFUTATION.search(new_text)


def introduces_unjustified_threshold(new_text: str) -> bool:
    """True when the edit sets a numeric policy constant with no sign of where the value came from.

    Deliberately narrow: only ALL-CAPS constants whose NAME declares them a boundary. A local
    variable or a tuned hyperparameter is not a policy claim; a module-level `_FLOOR` is.
    """
    if not _MAGIC_THRESHOLD.search(new_text or ""):
        return False
    return not _PROVENANCE.search(new_text or "")


def _load() -> dict[str, Any]:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def _save(state: dict[str, Any]) -> None:
    try:
        STATE.write_text(json.dumps(state))
    except Exception:
        pass


def is_gate_edit(path: str, new_text: str) -> bool:
    """A decision-rule change: a gate-ish PATH whose new text moves a boundary."""
    if not path or not path.endswith(_SOURCE_SUFFIXES):
        return False
    if not _GATE_PATH.search(path):
        return False
    return bool(_GATE_CONTENT.search(new_text or ""))


def is_verification(command: str) -> bool:
    """Did this shell command actually look at real data?"""
    return bool(_VERIFY_CMD.search(command or ""))


def _deny(path: str, *, licence: str = "", age_seconds: float = 0.0) -> None:
    # MEASURED: the previous message could not say WHAT had satisfied the window, because only a
    # timestamp was stored. Naming the last data command is what turns "you did not look" into a
    # checkable claim — and it is equally the tell when a passing licence was irrelevant.
    stale = ""
    if licence:
        stale = (
            f"\nThe last data command was {int(age_seconds // 60)} minutes ago:\n"
            f"    {licence}\n"
            "If that command was not about the rule you are changing, it never licensed this edit "
            "in the first place — recency is not relevance.\n"
        )
    reason = (
        "BLOCKED — gate edit without a preceding empirical check.\n\n"
        f"You are changing a decision rule in {path}, but no command in the last "
        f"{WINDOW_SECONDS // 60} minutes actually read the corpus this rule judges.\n"
        f"{stale}\n"
        "This is the exact failure from 2026-08-05: a promotion gate that was green on 139 tests, "
        "ruff and mypy — and a NO-OP on 27 of 28 real certs, while the money defect sat untouched "
        "in headline selection.\n\n"
        "Before this edit, RUN the data and answer with numbers:\n"
        "  1. How many REAL records does this gate currently pass that it should block?\n"
        "  2. How many does it block that it should pass?\n"
        "  3. If both are ~0, the gate is cosmetic — find the defect that actually costs money.\n\n"
        "Tests prove the code does what it says. Only DATA proves it was worth saying."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def _deny_magic_number(path: str) -> None:
    reason = (
        "BLOCKED — you are setting a policy THRESHOLD with no stated provenance.\n\n"
        f"{path} introduces a numeric boundary constant. Reading the corpus is not enough: it "
        "shows you looked at the data, not where the NUMBER came from.\n\n"
        "THE CASE (2026-08-10): `MAX_DD_FLOOR = -0.40` was copied into the domain layer from a "
        "research helper, with corpus reads in the same window — so this guard passed it. Asked "
        "'who decided that magic number and why?', there was no answer. It was the wrong SHAPE, "
        "not just the wrong value: published practice is drawdown relative to annualised return "
        "(CTA rule of thumb, Calmar >= 2), never an absolute cap. The fixed -0.40 admitted 7 of 8 "
        "candidate books and twice deleted the corpus's only pre-commitment survivor.\n\n"
        "Do ONE of these, then retry:\n"
        "  1. Cite the source in a comment — `PROVENANCE:` + a URL or a named standard; or\n"
        "  2. State the measurement that produced it (how many real records each side of the "
        "boundary, counted); or\n"
        "  3. Reuse the existing SoT constant instead of minting a second one.\n\n"
        "A threshold nobody can source is a rule you invented. Inventing gates is how good models "
        "get killed and bad ones get published."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def _deny_redecision(path: str) -> None:
    reason = (
        "BLOCKED — you are re-deciding a rule you already changed, with nothing said about what "
        "refuted the last version.\n\n"
        f"{path} was edited as a decision rule inside the last {WINDOW_SECONDS // 60} minutes, "
        "and this edit changes it again.\n\n"
        "Owner, 2026-08-14, after eight days: 'tomorrow you will say use this logic and that "
        "logic and output will be different than yesterday and you will change your mind'. A rule "
        "that moves between runs makes every number incomparable — yesterday's result cannot be "
        "checked against today's, so nothing ever ships.\n\n"
        "ITERATION IS NOT THE PROBLEM. The SELECT rule was rewritten three times in one turn and "
        "all three were right to make, because each cited the measurement that KILLED its "
        "predecessor: excluding all-in still froze -75% losers; ranking by MAR picks $10,030 on "
        "$10,000. That is science. Changing it again with no such evidence is drift.\n\n"
        "So say what refuted the previous rule, in the change itself:\n"
        "  * the measurement and its numbers ('MEASURED on N cells: ...'), or\n"
        "  * what the old rule got wrong, explicitly ('the old floor did not hold because ...').\n\n"
        "If you cannot name what refuted it, you are not fixing the rule — you are preferring a "
        "different one, and tomorrow you will prefer a third."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    event = payload.get("hook_event_name") or ""
    tool = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}

    if event == "PostToolUse" and tool == "Bash":
        command = str(tool_input.get("command", ""))
        if is_verification(command):
            state = _load()
            state["last_verified_at"] = time.time()
            # STORE THE COMMAND, not just the clock. Recency alone cannot tell an investigation
            # of the rule being changed from an unrelated `jq` 29 minutes earlier -- and the
            # unrelated one licensed the edit exactly as well. Now the licence is nameable, so
            # a denial can print what WOULD have satisfied it and a reviewer can see whether the
            # check was about the right thing.
            state["last_verified_cmd"] = command[:_LICENCE_EXCERPT_CHARS]
            _save(state)
        return 0

    # RECORD DECISION SITES AT PostToolUse, never at Pre. A PreToolUse recording would count an
    # edit that a sibling guard then DENIED, so the next attempt — the first one that would have
    # landed — reads as a re-decision. `todo_batch_guard` shipped with exactly that bug today.
    if event == "PostToolUse" and tool in {"Edit", "Write"}:
        path = str(tool_input.get("file_path", ""))
        new_text = str(tool_input.get("new_string") or tool_input.get("content") or "")
        if is_gate_edit(path, new_text):
            state = _load()
            state.setdefault("gate_edits", {})[path] = time.time()
            _save(state)
        return 0

    if event != "PreToolUse" or tool not in {"Edit", "Write"}:
        return 0

    path = str(tool_input.get("file_path", ""))
    new_text = str(tool_input.get("new_string") or tool_input.get("content") or "")
    if not is_gate_edit(path, new_text):
        return 0

    # A magic threshold denies REGARDLESS of the data-check window.
    #
    # This ordering is the whole point. `MAX_DD_FLOOR = -0.40` was introduced while corpus reads
    # were happening in the same window, so the check below waved it through. Reading data proves
    # you looked at the corpus; it does NOT prove the NUMBER came from anywhere. Those are two
    # questions and the guard only ever asked the first.
    if introduces_unjustified_threshold(new_text):
        _deny_magic_number(path)
        return 0

    # RE-DECIDING a rule already changed in this window. Checked before the data-window test
    # below, because a re-decision passes that test by construction: the corpus read that
    # licensed the FIRST change is still fresh when the second one lands.
    if redecides_without_refutation(path, new_text, _load(), now=time.time()):
        _deny_redecision(path)
        return 0

    # MEASURED, and it is what refuted the timestamp-only version: this guard passed a gate edit
    # today on corpus reads that had nothing to do with the constant being changed. Reading a
    # bare `last_verified_at` cannot distinguish an investigation of THIS rule from an unrelated
    # `jq` inside the window -- both set the same float. The licence is now carried alongside so
    # the denial can name it.
    state = _load()
    last = float(state.get("last_verified_at") or 0.0)
    if time.time() - last <= WINDOW_SECONDS:
        return 0

    _deny(path, licence=str(state.get("last_verified_cmd") or ""), age_seconds=time.time() - last)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)  # fail OPEN — never wedge the session
