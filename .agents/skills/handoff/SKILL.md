---
name: handoff
description: >-
  Hand the current session to the next one: measured state (commits, gates, deploys, open todos,
  hook round trips) written to ONE auto-loaded memory file, so a fresh session starts from facts
  instead of a summary. Use when context runs low, before a planned restart, or when the owner asks.
argument-hint: 'Optional: one line naming the goal the next session should pick up first.'
user-invocable: true
allowed-tools: Bash(git status *) Bash(git log *) Bash(python3 .claude/hooks/hook_denial_report.py *)
---

# Handoff (PulsAI)

IMPORTERS/CALLERS: `/handoff`, or the agent when context runs low.
AFFECTED API: none. Writes one memory file and its MEMORY.md index line.
DATA SCHEMAS: memory frontmatter (`name`, `description`, `metadata.type: project`).

Goal for the next session: $ARGUMENTS

## Measured state (run at invocation -- do not recall, read these)

Branch vs origin: !`git status -sb | head -1`

Unpushed commits (LOCAL ONLY -- a push to master is a prod deploy):
!`git log --oneline origin/master..HEAD`

Round-trip bill this session (tool denials by guard):
!`python3 .claude/hooks/hook_denial_report.py`

## Steps

1. Add what the injected state cannot show: the last gate result (`BE_RC=`/`FE_RC=` from the
   verify log, or "not run since `<sha>`"), deploy status if pushed
   (`railway status --json | jq -r '..|.latestDeployment?.status? // empty'`), background jobs
   still running with ABSOLUTE output paths, and open TodoWrite ids + status.
2. Write `~/.claude/projects/<project>/memory/handoff-latest.md`,
   overwriting the previous one. Frontmatter `name: handoff-latest`, `metadata.type: project`,
   then at most 60 lines:
   - **Goal** -- one sentence, the owner's words where possible.
   - **Shipped** -- sha + one line each, marked PUSHED or LOCAL ONLY (LOCAL ONLY first).
   - **Gates** -- each gate, its last exit code, and when it ran.
   - **Open** -- each open item with its NEXT COMMAND, not an intention.
   - **Traps** -- anything that cost a round trip or a wrong claim, with its fix.
   - **First three commands** for the next session.
3. Reference artifacts by path or sha; never paste a diff, a log or a plan into the handoff.
4. Secret check before saving: the file must contain no token, password, key, cookie or `.env`
   value. Grep the draft for `key|token|secret|password|Bearer|sk-` and remove any hit.
5. Add or refresh the `handoff-latest` line in MEMORY.md, then `head -5` the file to confirm it.
6. End with the quick-recap status line.

## Why a memory file

The SessionStart hook injects every memory body, so the next session reads the handoff with zero
tool calls. A scratch note is only found if someone looks, and the scratchpad path is per-session.
