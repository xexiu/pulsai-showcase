# diagnosing-bugs — Phase 1 is ALWAYS ON (MANDATORY)

Skill SoT: `.claude/skills/diagnosing-bugs/SKILL.md`. Guide: [aihero](https://www.aihero.dev/skills-diagnosing-bugs).

Owner, 2026-09-08: _"add @.claude/rules/diagnosing-bugs.md (SKILL) to you HOOK/S to ALWAYS Use
it when doing items, etc (ALWAYS), togheter with the other rules, skills, etc!!"_

## What changed, and why the old text was wrong to quote back at him

This file used to read _"User invoked only — do not auto-start the six-phase loop on light
questions (upstream over-fire #578)"_. That is now **superseded**. The owner's instruction wins,
and the previous line was a real contradiction: the skill was cited as always-relevant while the
rule said never auto-apply it.

But the resolution is not "run six phases on every question", because upstream #578 was a genuine
finding — the full loop over-fires on one-liners. The two reconcile because they are about
**different halves of the skill**:

| half                                                    | when                                                                           |
| ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| the six-phase **session** (repro → minimise → fix → PM) | user-invoked, `/diagnosing-bugs`, for a hard bug that deserves it              |
| **Phase 1's rule**                                      | **ALWAYS** — every item, every investigation, every "why is this slow / wrong" |

Phase 1's rule, in the skill's own words: _"If you catch yourself reading code to build a theory
before this command exists, stop — jumping straight to a hypothesis is the exact failure this
skill prevents. No red-capable command, no Phase 2."_

## The rule that is always on

**Before asserting a cause, name and RUN one command that goes red on the thing you are claiming.**
Show the invocation and its output. A theory built by reading code is a hypothesis, not a finding,
and must be labelled as one until a loop confirms it.

The loop must be red-capable (asserts the actual symptom, not "didn't crash"), deterministic, fast,
and agent-runnable — the skill's own four completion criteria for Phase 1.

## Two cases from the session that produced this rule, one each way

**It worked.** Asked why no hook had fired while the agent blocked on a four-minute gate, the first
answer was a REGEX THEORY read off `ALREADY_DETACHED`: "`\bnohup\b` probably matches the wrapper
filename and `[^|;]*&` probably catches the `&&`". Plausible, and **wrong in its specifics**. A
drive script — six real payloads through the live hook binary — was the red-capable loop, and it
immediately falsified its own first run (every case ALLOWED, including a control that must block)
because the payload was missing `hook_event_name`. Repaired, the loop isolated the true culprit:
not `&&` at all, but the `&` inside **`2>&1`**. The theory would have shipped the wrong fix.

**It was skipped, and cost a wrong claim.** Earlier the same session a prod page was answered with
"this is the funding warmer" before any correlation had been run. Running it (`railway logs`,
timestamps against sweep windows) supported two of three stalls and **refuted the third** — the
06:00:01 stall sat in no sweep window at all. Without the loop the report would have claimed
coverage of a stall the fix does not touch.

## Scope, so this does not become theatre

This is a rule about CAUSAL CLAIMS, not about every sentence. Reading code to understand it needs no
loop. Answering "where does X live" needs no loop. The rule binds the moment you say **"X is
happening BECAUSE Y"** — that is a claim about the running system, and the running system is the
only thing that can confirm it.

Companion to `.claude/rules/verify-and-judge-not-quote.md` (a docstring is a claim, not evidence)
and `.claude/rules/measure-before-after-on-both-environments.md` (a fix claim needs two numbers).
Those cover documents and fixes; this one covers diagnoses.

## Enforcement

`.claude/hooks/diagnosing_bugs_reminder.py` — a SessionStart injection, so the discipline is in
context from the first token of every session rather than only when someone types the slash
command. It is a REMINDER, not a blocker: no hook can separate a justified causal claim from an
unjustified one, and every guard that tried to judge prose was satisfied by rephrasing
(`todo_rules_reread_guard`'s own finding). What a hook CAN guarantee is that the standard is never
absent, which is what the owner asked for.

Complements Gortex exploration; hand off to `/improve-codebase-architecture` when no correct test
seam exists.
