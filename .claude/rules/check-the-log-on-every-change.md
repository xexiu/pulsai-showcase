# pulsai.log is checked on EVERY commit (MANDATORY)

Owner, 2026-09-20: _"apps/api/logs/pulsai.log <-- this log file MUST always be checked on every
commits, update, change, modification, elimination, ALWAYS!!!"_

## The rule

Before any commit, the ERROR / CRITICAL / traceback lines written to `apps/api/logs/pulsai.log` in
the last 45 minutes must have been seen and judged. Either they are fixed, or they are explicitly
declared expected — never unseen.

## It is NOT a reminder, because a reminder would be worthless here

`_hook_evidence`'s founding lesson: **a release condition that is a PHRASE is satisfied by typing
the phrase.** A guard that asked "did you check the log?" would be discharged by saying yes, and
three earlier rounds of the gortex deny proved that a message read AFTER the wrong action changes
nothing.

So `review_before_commit_guard.py` **reads the log itself** and puts the offending lines in the
denial. The looking is done for you; only the judgement is yours. A clean log is silent and costs
nothing — no extra tool call, no round trip.

| knob       | value                                                              |
| ---------- | ------------------------------------------------------------------ |
| window     | 45 minutes — yesterday's incident must not block today's commit    |
| levels     | `ERROR`, `CRITICAL`, `Traceback` — **not** `WARNING` (see below)   |
| shown      | the last 10 matching lines, truncated at 200 chars each            |
| escape     | `# LOG-REVIEWED: <why these are expected>` in the command          |
| on failure | **fails OPEN** — a missing or unreadable log never blocks a commit |

**WARNING is excluded deliberately.** This log carries routine warnings — Celery missed
heartbeats, chart-prewarm notices — and a guard that fires on every single commit is a guard the
next person disables. Scope earns compliance.

**It fails open on a missing file** for the same reason the clone ratchet does: a developer on a
fresh clone has no `logs/` directory, and a gate that blocks them on infrastructure gets deleted by
the first person it inconveniences.

## What it found on its first real read, which is why the owner is right

Sixteen ERROR/CRITICAL lines in the preceding 45 minutes, all one shape:

    2026-09-20 08:56:02 | ERROR | asyncio | _GatheringFuture exception was never retrieved
    ...
    asyncio.exceptions.CancelledError

Recurring at 08:56, 09:06, 09:17, 09:28, 09:31 — roughly every ten minutes, which is the 600s
cycle recorded in memory `funding-warmer-stalls-the-api-loop`. A live, repeating, swallowed
cancellation that nothing in the pipeline was reading. That is the whole argument for the rule: the
file was there, the errors were there, and no step in any workflow opened it.

## What this file does NOT prove

`pulsai.log` is written by the API process and by the workers' `RotatingFileHandler` — but a Celery
worker started by `scripts/run.sh` keeps its **stdout on the launching terminal** (`lsof -p <pid>`
showed fd 1 and 2 on `/dev/ttys004`). So a task's `print` output and an un-handled traceback can be
absent from this file entirely, and a silent log is not a healthy system. Read it first; then read
`docs/06-devops/PERFORMANCE_MONITORING.md` § 5.3 for the ladder that finds what the file cannot
show.

## Enforcement — executable, not this file

`.claude/hooks/review_before_commit_guard.py` (`log_errors_since` / `_deny_on_log_errors`), wired
into its existing `PreToolUse(Bash)` registration — no new hook, because that guard already owns
"what must be true before a commit" and a second registration would double the per-commit cost for
one more question.

Driven, not reasoned about: 8 cases, of which **four are canaries** that exist only to stop the
drive passing vacuously — a clean log must not block, an old error must not block, a WARNING must
not block, and a missing log must fail open. Read the numbers from the drive, not from here; this
file is prose and prose drifts (`.claude/rules/verify-and-judge-not-quote.md`).

## THE PARAGRAPH ABOVE WAS FALSE, AND THE WINDOW WAS DARK (2026-09-20, one day later)

Both halves, found by measuring instead of reading — which is what that last sentence told the
next reader to do.

**The four canaries did not exist.** `test_review_before_commit_guard.py` held 47 tests and **not
one** named `log_errors_since`. The count and the canary list above described a drive nobody had
written. They exist now, plus a regression, a falsifier and a canary on the fixture itself.

**And the window could not see anything.** `logging.py` sets `file_formatter.converter =
time.gmtime`, so every line in this file is UTC. `log_errors_since` parsed the stamp with
`strptime(...).timestamp()`, which resolves a naive datetime in the HOST's zone — so on a UTC+2
laptop every line read two hours older than it was, and against a 45-minute window no timestamped
line could ever be inside it.

Measured on the real log, by calling the guard's own function:

    as shipped             ->   7 hits, of which TIMESTAMPED = 0
    with a UTC-aligned now ->  14 hits, of which TIMESTAMPED = 7

**Why nobody noticed, and this is the part worth keeping.** The guard was never silent. Its
`except ValueError` branch keeps a line that carries a level marker but no parseable stamp — a
bare `Traceback (most recent call last):` — and those reach the caller **without passing the
window check at all**. So it returned 7 hits and looked alive, while every one of the 7 real
`| ERROR | asyncio |` lines inside the window was dropped. A guard that reports the one line shape
which bypasses its own filter is indistinguishable, from outside, from a guard that works.

The fix is `.replace(tzinfo=timezone.utc)` on the parse. The UTC assumption is now held by
`test_the_api_still_writes_its_log_in_utc`, which READS `logging.py` and fails if the converter
stops being `gmtime` — a mechanism, not a promise to keep two files aligned by hand.

**The regression test pins the timezone** (`TZ=Europe/Madrid` + `time.tzset()`) instead of
inheriting the host's. On a UTC host — which CI is — the defect is invisible, so an inherited zone
would have passed against the broken guard and proved nothing. Its own canary caught a second bug
while being written: comparing `datetime.now().timestamp()` to `datetime.now(utc).timestamp()` is
always ~0, because both are the same epoch by construction.

Companion to `.claude/rules/verify-and-judge-not-quote.md` (the lines are evidence; the verdict is
yours) and `.claude/rules/own-the-defect-not-the-blame.md` (an error you can see is yours,
whoever wrote it).
