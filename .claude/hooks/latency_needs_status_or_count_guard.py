#!/usr/bin/env python3
"""Block a latency claim about an endpoint that carries neither a STATUS CODE nor a SAMPLE COUNT.

REUSE-AUDIT: considered .claude/hooks/absence_needs_search_guard.py (a MISSING claim needs a
search, not an error message - same family, but its evidence is a search and its subject is
absence); .claude/hooks/kill_needs_ruin_reason_guard.py (a KILL needs a lost account - closest
in shape, "a verdict needs its evidence beside it", but scoped to trading verdicts and ruin
evidence); .claude/hooks/verdict_needs_sot_runner_guard.py (a tier must come from the SoT
runner - about WHO decides, not about whether a number measured what it claims);
.claude/hooks/finding_needs_todo_guard.py (a finding must become a todo - about tracking, not
provenance). None of them can express "this millisecond figure may have timed a rejection",
because none looks at latency at all. Extending any would have widened its subject past its
name. Not extending; new guard.

THE FAILURE, five times in one session (2026-09-06), three of them by this agent:

1. `cold_measure_warmup_exemptions.py` bucketed routes by latency without reading the status
   code, so `/api/v1/market/chart-indicators` answering **422 in 10 ms** was filed under
   "fast enough - a written reason is enough". It was exempted from warmup on that basis and
   then paged the owner for days at `p95=1.269s`.

2. The agent measured the same endpoint with `curl -o /dev/null` and NO token, and reported a
   table of "warm 130 ms" readings. Every one was an **HTTP 401 of 130 bytes**. It presented
   that as proof the warmer had fixed a 1.2 s problem.

3. `db INSERT [5m] critical p95=0.211s` was investigated as slow writes. The window held
   **n=12** samples at p50 61 ms: a p95 over twelve samples is barely more than the
   second-slowest one, and a single chunked upsert set it.

The shape is identical every time: a NUMBER that measured something other than what it appeared
to. Two disclosures make it checkable, and their absence is what let each one through:

* the STATUS CODE says the handler ran at all (a 4xx times the rejection, not the work);
* the SAMPLE COUNT says whether a percentile means anything (p95 over 12 is not a percentile).

WHY THIS RULE AND NOT "think harder". Every other guard for this family watches RHETORIC - a
citation without a verdict, a defer phrase beside a defect. This one is arithmetic: a latency
figure attributed to an endpoint either has its provenance beside it or it does not. Wording
cannot satisfy it and cannot evade it.

RELEASED by any of: an explicit status (`HTTP 200`, `status 200`, `-> 200`), a sample count
(`n=`, `samples`, `count=`), or an explicit disclosure that the reading was an error path
(`401`, `422`, `unauthenticated`, `rejected`) - because naming it is the honest case this
guard exists to encourage.

Fails OPEN. NOT bounded — it fires every time until the number carries its provenance.

That last word changed on 2026-09-06. This guard shipped with `MAX_BLOCKS = 2` enforced, and a
sweep found it was the ONLY one of twelve budgeted guards that actually honoured its cap; the
rest declare the constant and ignore it, per the owner's rule that a hook "MUST fire ALWAYS not
stay silent after X blocks". A cap here would have been worse than elsewhere, because nothing
scoped the counter to a session: the file outlives the conversation, so the third stop ever
would have been the last, on this machine and on every clone carrying that file.
"""

from __future__ import annotations

#: Derived from the registration this guard carries in settings.json, so
#: `register_guards --apply` can restore it if that file is ever regenerated.
HOOK_EVENT = ("Stop",)
HOOK_MATCHER = ""  # every stop; the predicate does the filtering

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_transcript import turn_text  # noqa: E402

STATE = Path(
    os.environ.get(
        "LATENCY_STATUS_STATE",
        Path(__file__).resolve().parent / ".latency_status_state.json",
    )
)
#: A TALLY, not a limit — deliberately not compared against anything. See the note in `main()`:
#: eleven of the twelve budgeted guards declare a cap and never read it, and the owner's rule is
#: that a guard fires until the thing it names is fixed. Kept because knowing how often this one
#: fires is useful; removed as a bound because outlasting a guard must not be an escape hatch.

#: A latency figure: "1045 ms", "0.207s", "p95=0.211", "p95 1.269s".
_LATENCY = re.compile(
    r"(?:\bp(?:50|95|99)\s*[=:]?\s*\d|\b\d{2,6}\s*ms\b|\b\d+\.\d+\s*s\b)",
    re.IGNORECASE,
)

#: The claim is ABOUT a served route. Without this the guard would fire on unrelated timings
#: (a test-suite duration, a build step), which are not this defect.
_ENDPOINT = re.compile(
    r"(?:/api/[\w/{}.-]*|\bendpoint\b|\broute\b|\bchart-indicators\b|\bohlcv\b)",
    re.IGNORECASE,
)

#: Provenance that makes the number checkable.
_HAS_STATUS = re.compile(
    r"(?:HTTP\s*\d{3}|status[\s=:]+\d{3}|->\s*\d{3}\b|\b[45]\d{2}\b|\b200\b"
    r"|unauthenticated|unauthorized|rejected|validator)",
    re.IGNORECASE,
)
_HAS_COUNT = re.compile(
    r"(?:\bn\s*=\s*\d|\bcount\s*[=:]\s*\d|\b\d+\s+samples?\b|\bsamples?\s*[=:]\s*\d"
    r"|\bover\s+\d+\s+samples?\b)",
    re.IGNORECASE,
)


def _load_blocks() -> int:
    try:
        return int(json.loads(STATE.read_text(encoding="utf-8")).get("blocks", 0))
    except Exception:
        return 0


def _save_blocks(count: int) -> None:
    try:
        STATE.write_text(json.dumps({"blocks": count}), encoding="utf-8")
    except Exception:
        pass


def verdict(text: str) -> bool:
    """True when the text reports an endpoint latency with no status and no sample count.

    Extracted so the decision is testable without constructing a hook payload.
    """
    if not text:
        return False
    if not (_LATENCY.search(text) and _ENDPOINT.search(text)):
        return False
    return not (_HAS_STATUS.search(text) or _HAS_COUNT.search(text))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0

    # `turn_text` takes the TRANSCRIPT PATH, not the payload. Passing the dict returns "" and
    # the guard silently never fires — which is exactly what happened on the first run: 12 unit
    # tests green against the predicate, and the hook itself exited 0 on the message it was
    # built for. A guard whose entry point is wrong is indistinguishable from one that agrees
    # with you, and that is the whole class of defect this guard exists to catch. Found by
    # driving it as a subprocess with a real JSONL transcript instead of trusting the units.
    try:
        text = turn_text(payload.get("transcript_path", "")) or ""
    except Exception:
        return 0

    if not verdict(text):
        return 0

    # NO BLOCK BOUND. The counter is kept as a TALLY, never as a limit.
    #
    # This guard shipped with `if blocks >= MAX_BLOCKS: return 0`, and a sweep on 2026-09-06
    # measured it as the ONLY one of twelve budgeted guards that actually enforced its bound --
    # every other declares MAX_BLOCKS and never reads it. So the newest guard was the one that
    # could go permanently silent, and worse than one-shot: nothing scoped `blocks` to a session,
    # so the state file outlives the conversation and the third stop ever would have been the
    # last, on this machine and on any clone carrying that file.
    #
    # The convention it should have followed is stated in `author_disclaimer_skip_guard`, quoting
    # the owner on 2026-08-28: "hook MUST fire ALWAYS not stay silent after X blocks". A release
    # after N attempts makes outlasting the guard an escape hatch -- the unprovenanced latency
    # figure simply ships on attempt N+1. The only exit is to add the status code or the count.
    _save_blocks(_load_blocks() + 1)

    sys.stderr.write(
        "STOP BLOCKED - an endpoint latency is reported with neither a STATUS CODE nor a\n"
        "SAMPLE COUNT beside it.\n\n"
        "Five times on 2026-09-06 a number measured something other than what it appeared to:\n"
        "  * 422 from the validator, timed as the route's speed -> exempted from warmup,\n"
        "    then paged the owner for days at p95=1.269s;\n"
        "  * curl -o /dev/null with no token -> a table of 'warm 130 ms' readings that were\n"
        "    all HTTP 401s of 130 bytes, presented as proof a 1.2 s problem was fixed;\n"
        "  * db INSERT critical p95=0.211s investigated as slow writes, over n=12 samples\n"
        "    with p50=61 ms - one chunked upsert set the p95.\n\n"
        "A 4xx times the REJECTION, not the work. A p95 over ~12 samples is not a percentile.\n\n"
        "Add one of:\n"
        "  * the status code you asserted (HTTP 200);\n"
        "  * the sample count behind the percentile (n=67);\n"
        "  * or say plainly that the reading was an error path (401 / 422 / unauthenticated).\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
