"""Shared ACTION-evidence ledger: what the agent DID this turn, not what it said.

WHY (owner, 2026-08-07): an audit of all 19 guards found 8 that read only `last_assistant_text`.
Those inspect WORDS, so they are passed by rephrasing — the owner proved it by making me probe my
own guard with a lazy line, which sailed through. A guard whose release condition is a PHRASE is
satisfied by typing the phrase.

This is the fix, written once instead of seven times: PostToolUse stamps a clock per evidence
KIND, and a Stop guard asks "did this turn actually DO it?" — a question no wording can answer.

    PostToolUse:  record(payload)                    # classify + stamp
    Stop:         if had("search"): release          # behaviour, not prose

Kinds are deliberately coarse; the point is "did an action of this class happen recently", not a
taxonomy. Fails OPEN everywhere: any error means "no evidence", which only makes a guard stricter,
never wedged.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

#: The DEFAULT ledger path. Read through `state_path()`, never directly -- see why below.
STATE = Path(
    os.environ.get(
        "HOOK_EVIDENCE_STATE",
        Path(__file__).resolve().parent / ".hook_evidence_state.json",
    )
)


def state_path() -> Path:
    """Where the ledger lives, resolved NOW rather than at import.

    MEASURED 2026-08-31: the live ledger collapsed to `{"search": ...}` mid-session, wiping
    `rules_read` and making `todo_rules_reread_guard` deny submissions minutes after the
    standards had genuinely been opened.

    `conftest.py` sets HOOK_EVIDENCE_STATE per test to prevent exactly that, and says so. But
    this module bound `STATE` at import -- which for a test run happens at COLLECTION, before
    any fixture executes -- so every guard imported in-process wrote to the REAL file and the
    suite overwrote the agent's own evidence. The seam existed and never reached the code.

    `STATE` stays as the default so a test may still monkeypatch it; the env var wins when set.
    """
    override = os.environ.get("HOOK_EVIDENCE_STATE")
    return Path(override) if override else STATE

#: How long an action counts as "this turn".
WINDOW_SECONDS = 30 * 60

#: Evidence kind -> what a command/tool looks like when it supplies that evidence.
PATTERNS: dict[str, re.Pattern[str]] = {
    # Looked something up before asserting it (grep, gortex, a read, a DB query).
    #
    # The `mcp__gortex__*` alternation is not decoration. MEASURED 2026-08-31:
    # `classify("mcp__gortex__search", ...)` returned an EMPTY set while
    # `classify("Bash", "grep -rn foo src/")` returned {"search"} -- so the only tool that could
    # stamp this kind was the one CLAUDE.md forbids, and a PreToolUse hook denies grep against
    # indexed source. Any guard keyed to `search` was therefore unsatisfiable by an agent
    # obeying the rules. The older split names below (search_text, find_usages, ...) still match
    # because the rename was additive and an older client still sends them.
    "search": re.compile(
        r"(grep|rg\b|search_text|search_symbols|find_usages|get_symbol_source|read_file"
        r"|mcp__gortex__(?:search|read|explore|relations|trace)"
        r"|rglob|glob\(|SELECT |information_schema|\bls\b|find )",
        re.IGNORECASE,
    ),
    # Re-computed a number rather than reasoning about it.
    "measurement": re.compile(
        r"(mark_to_market|verify_published_backtest_drawdown|measure_\w+|capital_cert"
        r"|capital_x_exit|_cert\.py|audit_|falsify|recheck|pytest|COUNT\(|psycopg2|asyncpg)",
        re.IGNORECASE,
    ),
    # Changed the code, i.e. fixed rather than described.
    "edit": re.compile(r"(Edit|Write|edit_file|write_file|edit_symbol|git commit|git apply)"),
    # Ran the thing instead of handing it over.
    "ran_command": re.compile(r"(run-with-nohup|python |pnpm |railway |curl |\./scripts/)"),
    # Asked the SOURCE what exists, rather than listing what we happen to hold.
    #
    # Added 2026-08-26 for `source_availability_guard`. The distinction it needs is NOT covered by
    # the kinds above: "search" deliberately matches `ls` / `find` / `glob` — inventory of our own
    # copy — and "ran_command" matches any bare `python ` or `./scripts/`. Neither can answer "does
    # this data exist upstream?". The incident: the OHLCV cache was listed, its earliest real-bar
    # file was 2021, and "real-bar history begins 2021-01-01, not 2017" was written into a script.
    # One Binance request refuted it — BTCUSDT returns real extremes from 2017-08-17; a bootstrap
    # had discarded the highs and lows on write. Inventory can support "our cache holds X"; it can
    # never support "X is all there is".
    "source_probe": re.compile(
        r"(\bcurl\b|\bwget\b|\brequests\b|\bhttpx\b|\burllib\b|\baiohttp\b"
        r"|\bccxt\b|fetch_ohlcv|\bklines\b|https?://)",
        re.IGNORECASE,
    ),
    # Opened the standards the todo list is supposed to be built against.
    #
    # Owner, 2026-08-13: a fresh todo list, a new item, and a finished list must each be preceded by
    # RE-READING the rules — coding standards, /tdd, /improve-codebase-architecture,
    # /architecture-hygiene-review, DDD_PATTERNS, ARCHITECTURE. All seven paths verified to exist
    # before this pattern was written; a guard keyed to a path that does not exist is a dead guard.
    "rules_read": re.compile(
        r"(coding-standards-mandatory|skills/tdd|improve-codebase-architecture"
        r"|architecture-hygiene-review|DDD_PATTERNS|ARCHITECTURE_PATTERNS|02-technical/ARCHITECTURE)",
        re.IGNORECASE,
    ),
    # Opened ARCHITECTURE_PATTERNS.md SPECIFICALLY — split out of `rules_read` on 2026-09-08.
    #
    # Owner: *"HOOKS should ALWAYS make you check and DEEP think of ARCHITECTURE_PATTERNS.md NOT
    # ONLY DDD_PATTERNS.md"* — after `architect_standards_guard` blocked a production write, was
    # satisfied by opening DDD_PATTERNS.md alone, and let the write through with no pattern
    # decision made at all. `rules_read` is an ANY-OF over seven paths, so the one document that
    # answers "which pattern, and why does its anti-fit not apply" could always be skipped by
    # opening a cheaper sibling.
    #
    # A SEPARATE kind rather than a narrowed `rules_read`: the any-of is correct for its own
    # question ("were the standards opened at all") and other guards depend on it, so narrowing
    # it would silently retighten all of them.
    "patterns_read": re.compile(r"ARCHITECTURE_PATTERNS", re.IGNORECASE),
    # ASKED PROD, rather than reading a local artifact and generalising from it.
    #
    # Owner, 2026-08-18: *"maybe cause localhost dev was not running 24/7 … Shouldn't you check PROD
    # railways?"* — after a one-row local JSONL became "the tape never ran", while prod held 44
    # daily rows of it. Local dev is intermittent by nature, so a local file is evidence about this
    # laptop and nothing more. Deliberately does NOT include filesystem search: the disk WAS
    # searched that day, exhaustively, and the conclusion was still false.
    "prod_checked": re.compile(
        r"(DATABASE_PUBLIC_URL|\brailway\b|/api/v1/admin|psycopg2?\b|asyncpg"
        r"|prod(uction)?[ _-](db|database|table)|queried prod|checked prod)",
        re.IGNORECASE,
    ),
    # CONTACTED each environment, judged by the URL the command actually names.
    #
    # Owner, 2026-09-07: *"validage ALWAYS localhost dev AND prod!!!!! ALWAYS!!!"* — after PERF-40
    # was declared PASS from a PROD-only measurement, so the improvement was never differentially
    # attributed and is equally consistent with a deploy or a warm cache.
    #
    # Split from `prod_checked` on purpose. That kind matches `psycopg2` and `/api/v1/admin`, which
    # a LOCALHOST admin call also matches — fine for "did you ask a database rather than a file",
    # useless for "which of the two environments was this". These two demand a real URL, so the
    # bare WORD localhost in a doc or a grep can never release a guard that reads them.
    "validated_prod": re.compile(r"https?://(?:[\w.-]+\.)?pulsai\.live", re.IGNORECASE),
    # THE TWO PROD TARGETS, told apart. Added 2026-09-14, because `validated_prod` above CANNOT
    # tell them apart: its optional `[\w.-]+\.` matches `api.pulsai.live` and bare `pulsai.live`
    # identically, so every guard reading it treats "I probed the API" as "I checked production".
    #
    # `git push origin master` deploys BOTH: the API to Railway and the frontend to VERCEL.
    # Measured that day -- `api.pulsai.live` was probed all session and reported as prod while
    # `pulsai.live/en/chart` answered 404, three Vercel builds having failed with nobody watching
    # that half. The owner found it from deploy emails, not from me.
    #
    # `validated_site_prod` excludes the `api.` host with a negative lookahead, so hitting the API
    # can never satisfy the SITE. That exclusion is the entire point of the split.
    "validated_api_prod": re.compile(r"https?://api\.pulsai\.live", re.IGNORECASE),
    "validated_site_prod": re.compile(r"https?://(?!api\.)(?:www\.)?pulsai\.live", re.IGNORECASE),
    # The prod LOGS, which an HTTP 200 does not read. Owner, 2026-09-20, after a push reported
    # verified on three green curls: "you verifying apis, good, but what about railways logs???
    # we have a script for this to verify logs for criticals, warnings, performance, billing,
    # EVERYTHING". A 200 says the door opens; it says nothing about what the service is throwing
    # behind it — the same distinction `pulsai.log` already enforces for localhost.
    #
    # Matched on the SCRIPT or the `railway logs` command, never on prose: this module's founding
    # lesson is that a release condition which is a PHRASE is satisfied by typing the phrase.
    "checked_railway_logs": re.compile(
        r"check_railway_logs\.py|railway-log-watch|\brailway\s+logs\b", re.IGNORECASE
    ),
    # THE DEPLOYED SHA. `/health` answers `{"version": "0.1.0+<short sha>"}`, so prod can say
    # which commit it is actually running — and on 2026-09-20 it said `5351cf7c` while HEAD was
    # `933fed352`, SEVEN commits ahead, with Railway still BUILDING. Three green 200s had already
    # been reported as "both prod targets verified"; every one of them hit the OLD build.
    #
    # Owner, the same day: "ALWAYS check after push and railways deploy your push git version
    # sha". A status code proves a door opens. Only the sha proves it opens onto YOUR code.
    #
    # Requires the health URL AND a version/sha token in the same command, so a bare
    # `curl .../health` (which already satisfies `validated_api_prod`) cannot silently discharge
    # this too. Satisfied by: curl -s https://api.pulsai.live/health | jq -r .version
    "checked_deployed_sha": re.compile(
        r"(?=.*pulsai\.live/health)(?=.*(?:version|sha|commit))", re.IGNORECASE | re.DOTALL
    ),
    # The admin surfaces that REGISTER what happened, as opposed to the raw service logs:
    # /api/v1/admin/logs, /api/v1/admin/audit and /api/v1/admin/abuse-log are what the UI reads.
    "checked_prod_audit": re.compile(r"/admin/(?:logs|audit|abuse-log)\b", re.IGNORECASE),
    # A push IS a deployment (.claude/rules/push-is-a-prod-deploy.md), so this is the trigger that
    # makes deployment verification OWED. Matched on the COMMAND, never on prose about pushing --
    # prose is what rephrasing defeats.
    "pushed_to_remote": re.compile(r"\bgit\s+push\b", re.IGNORECASE),
    # A push whose DESTINATION names a protected branch (`origin master`, `HEAD:master`), whatever
    # branch is checked out. `pushed_to_remote` alone cannot tell a PR-branch push (no deploy) from
    # this one. Names mirror `commit_must_ship_guard._PROTECTED_BRANCHES_FALLBACK`.
    "pushed_to_protected": re.compile(r"\bgit\s+push\b[^|;&\n]*?[\s:](?:master|main)\b", re.IGNORECASE),
    "validated_local": re.compile(
        r"https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0)(?::\d+)?",
        re.IGNORECASE,
    ),
    # THE VENUE: the live engine's path to Lighter, which the served API never takes. Owner, 2026-10-28 (asked,
    # "yes please"): the order client's nonce warm-up measured 315 ms -> 0.2 ms engine -> Lighter mainnet, and
    # neither URL above could record it. The URL itself, never the `MAINNET` constant: a default target is invisible.
    "validated_venue": re.compile(r"https?://mainnet\.zklighter\.elliot\.ai", re.IGNORECASE),
    # THE PLAN ITSELF. A todo that cites a slice id (`D-7`, `C-5a`, `P0-2`) is claiming to follow
    # the plan, and the only evidence for that is having OPENED the file the slice lives in.
    #
    # Owner, 2026-09-20: *"your INVENTING YOURSELF EVERYTHING!!! ... ENFORCE HOOKS"*. Measured: a
    # todo read `D-7 ... after C-2 and C-5` while the plan's D-7 row names its dependency as `D`
    # and never mentions C-2 — an invented precondition, re-sent ~40 times, which delayed a slice
    # whose gate half was already built.
    #
    # Matched on the PATH, so any reader counts: native `Read`, gortex `target.file`, or the
    # `grep`/`sed` that is how a 1,400-line plan row actually gets opened.
    # Consumer: `plan_slice_must_be_read_guard.py`, which reads this straight off PATTERNS.
    "plan_read": re.compile(r"/\.claude/plans/[\w.-]+\.md", re.IGNORECASE),
    # THE THREE SoT MONEY ENDPOINTS. They are here rather than inside one guard because "was the
    # cert actually run" is a question more than one guard will ask, and a regex copied into a
    # guard is a regex that drifts from the route it is supposed to track.
    #
    # Matched on the route PATH, so any door reaches them: curl on the command line, a python
    # client that prints the URL it called, or the endpoint named in a request log. Owner,
    # 2026-09-20: *"everything must be run and cert with sot endpoints (cert, precommit and money
    # standings) both local + prod"* — after I ran two of the three and reported as if done.
    #
    # The three are NOT interchangeable: select-confirm grades ONE pre-committed cell and so pins
    # ONE lane, cert-run produces the whole lane ladder, money-standings is what the rest of the
    # system reads. Consumer: `three_sot_endpoints_guard.py`, which reads these straight off
    # PATTERNS rather than through `record` — the endpoint is often visible only in a command's
    # OUTPUT, and pushing output through `classify` would stamp a dozen unrelated kinds.
    "sot_cert_run": re.compile(r"/research-loop/cert-run", re.IGNORECASE),
    "sot_select_confirm": re.compile(r"/research-loop/select-confirm", re.IGNORECASE),
    "sot_money_standings": re.compile(r"/research-registry/money-standings", re.IGNORECASE),
    # ACTUALLY tracked owed work, rather than typing the word "tracked".
    #
    # Owner, 2026-08-13: *"IF findings, add auto to your TODO list to track and fix them"* — after
    # catching me narrate a scope gap and move on. `named_gap_guard` was supposed to stop that, but
    # its release condition matched the STRING `todo`/`TodoWrite`, so the sentence "tracking it"
    # released a turn in which nothing was tracked. That is precisely the phrase-satisfies-guard
    # defect this whole module exists to fix, surviving inside a guard built on this module.
    #
    # Matched on the tool NAME, so it is the call that counts, never the prose.
    "todo": re.compile(r"\bTodoWrite\b"),
    # RAN THE REPO INVENTORY, rather than recalling what the repo holds. Owner, 2026-10-26: "are you
    # 100% DEE PSearched ... build a tool script to ALWAYS run it on every session, item, todo list" --
    # after "what the repo has" was answered twice by repeating his own list. Matched on the MODULE
    # INVOCATION, never on the word: `grep repo_inventory` or editing the file does not count.
    # Consumer: `repo_inventory_hook.py` (it also stamps this itself when it runs the inventory).
    "repo_inventory": re.compile(r"-m\s+src\.lib\.repo_inventory\b"),
}


def _load() -> dict[str, Any]:
    try:
        data = json.loads(state_path().read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save(state: dict[str, Any]) -> None:
    """Write ATOMICALLY: a reader must never observe a half-written ledger.

    `_load()` returns `{}` for anything it cannot parse, so a torn file does not merely lose the
    bytes in flight — the next `record()` merges onto `{}` and erases EVERY kind. Writing to a
    temp file in the same directory and `os.replace`-ing it makes the swap atomic on POSIX.
    """
    try:
        path = state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state))
        os.replace(tmp, path)
    except Exception:
        pass


@contextmanager
def _locked() -> Iterator[None]:
    """Serialize read-modify-write across guard SUBPROCESSES.

    MEASURED 2026-08-18: several PostToolUse guards call `record()` for the SAME tool call, in
    parallel processes. Each did load -> mutate -> save with no lock, so the last writer's stale
    snapshot overwrote every key the others had added. Four concurrent writers ended with a ledger
    holding ONE kind — and the live ledger was repeatedly found holding exactly `['edit']`, which
    is how a turn that had genuinely opened the standards got told "no tool call opened any of
    these".

    Fails OPEN: if the lock cannot be taken (unsupported filesystem, permissions), the write still
    proceeds. A guard must never wedge the session over its own bookkeeping.
    """
    path = state_path()
    lock_path = path.with_name(f"{path.name}.lock")
    handle = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+")  # noqa: SIM115 - released in the finally below
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    except Exception:
        handle = None
    try:
        yield
    finally:
        if handle is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def classify(tool_name: str, command: str) -> set[str]:
    """Which evidence kinds this tool call supplies."""
    blob = f"{tool_name} {command}"
    kinds = {kind for kind, rx in PATTERNS.items() if rx.search(blob)}
    # A tool call that edits is an edit regardless of its command text.
    if tool_name in {"Edit", "Write", "NotebookEdit"} or "edit_file" in tool_name or "write_file" in tool_name:
        kinds.add("edit")
    return kinds


#: Evidence kinds that assert a DOCUMENT WAS READ, not merely that a path was named.
_WHOLE_FILE_KINDS = frozenset({"rules_read", "patterns_read"})

#: Scores how much of a document a SHELL command emitted. `covers_whole_file` below answers the
#: same question for the Read tool; that fix (2026-09-12) left the Bash path -- the one CLAUDE.md
#: MANDATES in auto mode -- crediting `wc -l` as a full read. See `_hook_read_span`.
import _hook_read_span as read_span  # noqa: E402


def covers_whole_file(tool_input: dict[str, Any]) -> bool:
    """True when a read spans the file end to end.

    MEASURED 2026-09-12: `record()` classified from the PATH STRING alone, so
    `Read(DDD_PATTERNS.md, limit=120)` stamped `rules_read` exactly as a full read did. The
    standards were duly "opened" and two of them were read 120 lines deep. The owner: "Have you
    resd ALL the rules, ALLthe skills, aall the docs, EVERYTHING ... or doing what ever tou
    want???"

    This is this module's own founding lesson turned on itself -- "a release condition that is a
    phrase is satisfied by typing the phrase" -- with a PATH in place of the phrase.

    Fails OPEN on anything it cannot measure (no path, unreadable file, empty file), because a
    guard that punishes a read it failed to inspect teaches people to route around the rule.
    """
    offset = tool_input.get("offset")
    limit = tool_input.get("limit")
    if not offset and not limit:
        return True

    raw = tool_input.get("file_path") or tool_input.get("path")
    if not raw:
        target = tool_input.get("target")
        raw = target.get("file") if isinstance(target, dict) else None
    if not raw:
        return True

    path = Path(str(raw))
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    try:
        total = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return True
    if total == 0:
        return True

    # `Read` counts lines from 1 and `limit` is a COUNT, so the last line reached is
    # start + limit - 1. A read starting past line 1, or stopping before the end, is partial.
    start = int(offset) if offset else 1
    end = start + int(limit) - 1 if limit else total
    return start <= 1 and end >= total


def record(payload: dict[str, Any], *, now: float | None = None) -> set[str]:
    """PostToolUse: stamp every evidence kind this call supplies. Returns the kinds recorded."""
    stamp = time.time() if now is None else now
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or "")
    if not command:
        # Non-Bash tools still carry a target worth recording, under DIFFERENT keys: native
        # Read/Edit/Write send `file_path`, every gortex tool sends `path`. Reading only
        # `file_path` made the MANDATED tooling invisible here — CLAUDE.md denies `Read` on
        # indexed source, so `rules_read` could never be stamped and `todo_rules_reread_guard`
        # denied every submission no matter how much reading had been done (measured 2026-08-18).
        # `target.file` is the CONSOLIDATED gortex surface: read/edit send the path nested
        # there, not as `file_path` or `path`. Measured 2026-08-31 -- without this the ledger
        # recorded `search` (matched on the tool NAME) and never `rules_read`, so opening the
        # standards with the MANDATED tool could not satisfy `todo_rules_reread_guard` while
        # `Read` stays denied on indexed source. Same class as the `path` fallback beside it.
        target = tool_input.get("target")
        nested = target.get("file") if isinstance(target, dict) else None
        command = str(tool_input.get("file_path") or tool_input.get("path") or nested or "")

    kinds = classify(tool_name, command)
    # The SHELL text, not the path fallback above: only a real Bash payload can be scored by
    # read EXTENT, and `command` may by now hold a file_path from a Read/gortex call.
    shell_command = str((payload.get("tool_input") or {}).get("command") or "")
    # A timestamp says a TodoWrite happened; it cannot say WHICH gap it covered. Store the item
    # text so a guard can ask "was THIS one tracked?" — the hole that let "owed and tracked" pass
    # for an item never added (owner, 2026-08-14).
    todo_text = ""
    if "todo" in kinds:
        todos = (payload.get("tool_input") or {}).get("todos") or []
        todo_text = " ".join(str(t.get("content") or "") for t in todos if isinstance(t, dict))[:8000]

    if not kinds:
        return set()

    # LOAD AND SAVE INSIDE ONE LOCK. Reading outside it and writing inside is the same race with
    # extra steps: the snapshot goes stale between the two, and the merge writes back keys that
    # another process has already superseded.
    #
    # The whole-file decision lives INSIDE the lock too, because the Bash half is cumulative:
    # `sed -n '1,60p'` then `sed -n '60,212p'` is a complete read of a 212-line document, and
    # deciding that needs the ranges already recorded. Reading them outside the lock would race
    # exactly as the kinds did (measured 2026-08-18, four writers, one surviving key).
    with _locked():
        state = _load()
        # OPENING IS NOT READING. `classify` sees only the path string, so a truncated look at a
        # standard was indistinguishable from reading it. Strip the document kinds when the read
        # demonstrably stopped short; every other kind is unaffected.
        if kinds & _WHOLE_FILE_KINDS:
            if shell_command:
                prior = state.get("_spans")
                satisfied, spans = read_span.bash_whole_file_kinds(
                    shell_command, prior if isinstance(prior, dict) else {}
                )
                state["_spans"] = spans
                kinds -= _WHOLE_FILE_KINDS - satisfied
            elif not covers_whole_file(tool_input):
                kinds -= _WHOLE_FILE_KINDS
        for kind in kinds:
            state[kind] = stamp
        if todo_text:
            # The ledger BEFORE this write, so a guard that first sees a promise on the very
            # TodoWrite recording it can ask what the write ADDED (finding_needs_todo_guard).
            if state.get("todo_text") != todo_text:
                state["todo_prev_text"] = state.get("todo_text", "")
            state["todo_text"] = todo_text
        _save(state)
    return kinds


def stamp(kind: str, *, now: float | None = None) -> None:
    """Stamp ``kind`` directly -- for a hook that DID the action itself, which no tool call carries
    (`repo_inventory_hook` runs the inventory and puts it into context). Fails OPEN, never raises."""
    try:
        with _locked():
            state = _load()
            state[kind] = time.time() if now is None else now
            _save(state)
    except Exception:
        pass


def stamped_at(kind: str) -> float:
    """Epoch seconds of the last action of this kind, or 0.0 when none (or unreadable).

    For a guard whose evidence should live until something OTHER than a clock says it lapsed --
    `architect_standards_guard` asks "has the context been compacted since the doc was read".
    """
    try:
        return float(_load().get(kind, 0.0))
    except Exception:
        return 0.0


def had(kind: str, *, now: float | None = None, window: int = WINDOW_SECONDS) -> bool:
    """Stop: did an action of this kind happen recently? Fails to False (stricter), never raises."""
    try:
        stamp = float(_load().get(kind, 0.0))
    except Exception:
        return False
    if stamp <= 0.0:
        return False
    current = time.time() if now is None else now
    return (current - stamp) <= window


def clear() -> None:
    """Reset the ledger (tests)."""
    _save({})


def recorded_text(kind: str) -> str:
    """The CONTENT most recently supplied for ``kind``, or "" when nothing was recorded.

    Only "todo" writes content today. A guard that must ask WHICH item was tracked -- rather than
    merely whether some TodoWrite happened -- reads this. Fails to "" (stricter: an unreadable
    ledger cannot release a guard), never raises.
    """
    try:
        value = _load().get(f"{kind}_text", "")
    except Exception:
        return ""
    return str(value) if isinstance(value, str) else ""
