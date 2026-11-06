#!/usr/bin/env python3
"""Stop hook: you called your OWN number incomplete and shipped it anyway.

Importers/callers: Claude Code `Stop`, registered in `.claude/settings.json`; and
`test_incomplete_measurement_guard.py`. Affected API: none -- it emits a hook decision on stdout.
Data schemas: the hook payload (`transcript_path`) and the turn's assistant text.

THE CASE, 2026-09-09. Asked whether we could publish whale stop-loss levels, I probed the venue,
counted the trigger orders, and reported the count with this attached:

    "One caveat I have to state rather than bury: my count is a LOWER BOUND. The payload has a
     `children` key ... so the real count could be materially higher. I'm not going to guess."

Then I stopped. The owner: "what is this??? fixed/improvred/addressed? or.. its ok/normal/correcT???"
He was right, and closing it took under a minute.

PROBED: POST https://api.hyperliquid.xyz/info {"type":"frontendOpenOrders"} over 60 leaderboard
addresses returned 8,738 Limit + 2 Stop Market top-level; re-probed descending into `children`,
returned 8,654 Limit + the same 2 Stop Market. The descent changed nothing -- which is a real
answer, and the one the caveat had been standing in for. Those counts describe THAT SAMPLE at that
moment and are not a claim about what the venue holds.

WHY NO EXISTING GUARD CAUGHT IT, which is the part worth encoding. `architect_no_defer_guard`
fires on defer LANGUAGE over a confirmed defect -- "later", "not urgent", "low priority" -- and
none of that appears above; the sentence is careful, honest, and reads as rigour.
`todo_completion_guard` fired, but it cannot tell "blocked on a compute I started" from "I
declared my own measurement partial and walked away". `absence_needs_search_guard` wants a search
behind a claim that something does not exist -- a different claim. `agreement_without_action_guard`
wants action behind agreeing with the owner -- a different trigger.

And critically, the defer/todo guards treat TRACKING as sufficient: the recount WAS written into
the todo list as its own item, which is exactly the escape hatch they offer. Tracking became a
substitute for a one-minute re-run.

So the gap is specific: nobody was watching for an author admitting their OWN number is partial.
That is unusually detectable precisely BECAUSE the author volunteers it -- unlike "is this causal
claim justified", which no hook can judge, this one arrives pre-labelled.

WHAT IT DOES NOT DO. It does not judge whether a number is right, complete, or worth having. It
fires only on a self-declared gap in a MEASUREMENT the same turn reports, and releases the moment
the turn shows the gap closed or states why closing it is blocked. Honest partial reporting stays
legal; silently living with the partial does not.
"""

from __future__ import annotations

#: Derived from the registration this guard already carries in settings.json (Stop, no matcher),
#: so `register_guards --apply` can restore it if that file is ever regenerated. Was undeclared --
#: wired but not re-wirable, flagged by `register_guards.py --check` and fixed here rather than
#: left as a note (own-the-defect-not-the-blame.md).
HOOK_EVENT = "Stop"

import json
import re
import sys
from pathlib import Path

#: The author admitting their own figure is partial. Each of these is a phrase a careful writer
#: reaches for when they know the number is not the whole answer -- which is the tell.
_ADMISSION = re.compile(
    r"\b(?:"
    r"lower bound"
    r"|upper bound"
    r"|under-?count(?:s|ed|ing)?"
    r"|over-?count(?:s|ed|ing)?"
    r"|(?:could|may|might) be (?:materially |much |significantly )?higher"
    r"|(?:could|may|might) be (?:materially |much |significantly )?lower"
    r"|(?:did|do) not (?:descend|recurse|include|count|check|measure|cover)"
    r"|(?:have|has) not (?:yet )?(?:counted|measured|checked|verified)"
    r"|only (?:counted|measured|checked|sampled|looked at)"
    r"|(?:partial|incomplete) (?:count|measurement|sample|scan|sweep)"
    r"|not (?:the )?(?:whole|full) (?:count|picture|answer)"
    r")\b",
    re.IGNORECASE,
)

#: A figure the admission could be ABOUT. Without one this is prose, not a measurement -- the
#: guard must not fire on "I did not check the docs".
_HAS_FIGURE = re.compile(r"\d")

#: The gap was closed IN THIS TURN. A recount, a corrected figure, an explicit re-run.
_CLOSED = re.compile(
    r"\b(?:"
    r"re-?count(?:ed|ing)?"
    r"|re-?measur(?:ed|ing)"
    r"|re-?ran|re-?run(?:ning)?"
    r"|re-?prob(?:e|ed|ing)"
    r"|now includes?"
    r"|descend(?:ed|ing) into"
    r"|closed the (?:gap|caveat)"
    r"|settled it"
    r"|changed nothing"
    r"|confirmed the (?:count|figure|number)"
    r")\b",
    re.IGNORECASE,
)

#: The deliberate escape: closing it is genuinely blocked, and the reason is stated.
_DECLARED_PARTIAL = re.compile(r"MEASUREMENT-PARTIAL:\s*\S", re.IGNORECASE)

_REASON = (
    "BLOCKED — you called your OWN number incomplete and stopped anyway.\n"
    "\n"
    "A self-declared partial measurement is not rigour, it is an unfinished job wearing rigour's\n"
    "clothes. THE CASE (2026-09-09): a whale stop-order count was published as a LOWER BOUND\n"
    "because the probe never descended into the payload's `children`. Re-running it with the\n"
    "descent took under a minute and settled the question — the count was unchanged. The owner\n"
    "had to ask: 'what is this??? fixed/improvred/addressed? or.. its ok/normal/correcT???'\n"
    "\n"
    "TRACKING IT IS NOT CLOSING IT. `architect_no_defer_guard` and `todo_completion_guard` both\n"
    "accept a todo item as sufficient, which is exactly how this slipped: the recount WAS tracked,\n"
    "and tracking became a substitute for a one-minute re-run.\n"
    "\n"
    "Do one:\n"
    "  * CLOSE it — re-run the measurement without the gap and report what changed (often nothing,\n"
    "    which is itself the answer); or\n"
    "  * say why closing it is blocked, in the message:\n"
    "        MEASUREMENT-PARTIAL: <what blocks the complete count>\n"
)


def turn_text(transcript_path: str) -> str:
    """Every assistant message in the current turn, newest last. Empty when unreadable."""
    path = Path(transcript_path)
    if not transcript_path or not path.is_file():
        return ""
    collected: list[str] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") == "user":
                collected.clear()  # a user turn starts a new turn
                continue
            if row.get("type") != "assistant":
                continue
            content = row.get("message", {}).get("content")
            if isinstance(content, str):
                collected.append(content)
            elif isinstance(content, list):
                collected.extend(part.get("text", "") for part in content if isinstance(part, dict))
    except OSError:
        return ""
    return "\n".join(collected)


def ships_an_admitted_gap(text: str) -> bool:
    """True when the turn admits its own measurement is partial and neither closes nor declares it."""
    if not _ADMISSION.search(text):
        return False
    if not _HAS_FIGURE.search(text):
        return False
    if _DECLARED_PARTIAL.search(text):
        return False
    return not _CLOSED.search(text)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail OPEN

    if payload.get("tool_name"):
        return 0

    text = turn_text(str(payload.get("transcript_path") or ""))
    if not text or not ships_an_admitted_gap(text):
        return 0

    print(json.dumps({"decision": "block", "reason": _REASON}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)  # fail OPEN
