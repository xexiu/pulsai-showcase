---
name: code-review
description: >-
  Two-axis Standards+Spec review of <fixed-point>...HEAD (committed only).
  User-invoked in PulsAI as /code-review with an explicit fixed point — not Claude
  Code's built-in bug-hunt /code-review; not caveman-review (terse PR comments).
disable-model-invocation: true
---

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards** — does the code conform to this repo's documented coding standards?
- **Spec** — does the code faithfully implement the originating issue / spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

The issue tracker should have been provided to you — see `docs/agents/issue-tracker.md` (already present in PulsAI).

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point — a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. If they didn't specify one, ask for it.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here — not inside two parallel sub-agents.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. Issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`, etc.) — fetch via the workflow in `docs/agents/issue-tracker.md`.
2. A path the user passed as an argument.
3. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

### 3. Identify the standards sources

Anything in the repo that documents how code should be written, such as `CODING_STANDARDS.md` or `CONTRIBUTING.md`.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below — a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation — and, like any standard here, skip anything tooling already enforces.

Each smell reads _what it is_ → _how to fix_; match it against the diff:

- **Mysterious Name** — a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code** — the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy** — a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps** — the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches** — the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change** — one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality** — abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man** — a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest** — a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### 4. Spawn both sub-agents in parallel

**Standards sub-agent prompt** — include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, **plus the smell baseline from step 3** pasted in full — the sub-agent has no other access to it.
- The brief: "Report — per file/hunk where relevant — (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls — documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words. **Do not invoke `/code-review` or spawn additional agents — perform this review directly.**"

**Spec sub-agent prompt** — include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words. **Do not invoke `/code-review` or spawn additional agents — perform this review directly.**"

If the spec is missing, skip the Spec sub-agent and note this in the final report.

### 5. Validate

While the sub-agents run, run the gates this repo already documents — and record pass/fail:

```bash
cd apps/web && pnpm verify          # type-check, lint, full test run
cd apps/api && ./scripts/verify.sh  # mypy, ruff, full pytest suite
```

Run only the side the diff touches (FE-only diff → skip the BE gate, and say so). A skipped gate is reported as `Skipped`, never as `Pass`.

Why this belongs here: the two axes read the diff and reason about it. Neither one _runs_ anything, so a review could cite `pnpm verify` as the standard and never learn that it fails. Reviewing code while the gate it is measured against is red produces confident findings about a build that does not work.

### 6. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings — the two axes are deliberately separate (see _Why two axes_).

Then a gate table, so the reader sees what was actually executed rather than what was cited:

| Gate                          | Result                |
| ----------------------------- | --------------------- |
| Frontend `pnpm verify`        | Pass / Fail / Skipped |
| Backend `./scripts/verify.sh` | Pass / Fail / Skipped |

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes — that's the reranking the separation exists to prevent.

### 7. State a verdict, per axis

A review that ends on counts leaves the decision to whoever reads it. Say it outright, and keep the axes separate here too:

| Condition                                                                             | Verdict                |
| ------------------------------------------------------------------------------------- | ---------------------- |
| No findings on that axis, and no gate on the touched side failed                      | **PASS**               |
| Findings that are judgement calls only (baseline smells, style)                       | **PASS WITH COMMENTS** |
| A documented-standard breach, a missing/incorrect spec requirement, or a failing gate | **CHANGES NEEDED**     |

Two verdicts, never one: Standards and Spec can disagree, and collapsing them re-introduces the masking the two-axis split exists to prevent. A failing gate makes the Standards axis `CHANGES NEEDED` regardless of what the diff reads like — a red gate is not a judgement call.

These are verdicts on a **review**, not merge permissions. Nothing here approves or blocks a PR; that stays a human decision.

### 8. Write the artifact

Save the aggregated report to `.claude/reviews/<fixed-point>..HEAD-<date>.md` and give the reader the path.

A review that exists only in a session transcript cannot be re-read when the fix lands, cited in the PR, or compared against the next review of the same branch. The file is the deliverable; the transcript is where it happened to be produced.

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.

## PulsAI usage (mandatory)

Guide: [aihero](https://www.aihero.dev/skills-code-review).

### Name collision

Claude Code ships a **different** built-in `/code-review` (bug-hunt). This skill is **Standards + Spec**. PulsAI keeps `disable-model-invocation: true` — type `/code-review` only when you want **this** skill, and say the fixed point (`/code-review since master`). For terse PR comments use `/caveman-review`. For security/bugbot use those dedicated flows.

### Anti-nesting

Sub-agents must **not** re-invoke `/code-review` or spawn further review agents (upstream fan-out to 50+ agents). The brief lines above are mandatory. Parent spawns **exactly two** Sonnet subagents (Standards + Spec), then aggregates.

### Adopted from ECC

`ecc@ecc` ships its own `/ecc:code-review`. Both were read in full on 2026-09-01. They are
complementary, not duplicates: ECC's asks _should this PR merge_, this one asks _is it right,
and is it what was asked for_. ECC has no Spec axis at all — code can pass all seven of its
categories and still implement the wrong thing.

Taken from it, because this skill genuinely lacked them: the **Validate** phase (step 5), the
**gate table** (step 6), the **verdict** (step 7) and the **artifact path** (step 8).

Refused, deliberately — record the reasons, because each looks like a gap otherwise:

- **ECC's thresholds** (functions > 50 lines, files > 800) **contradict**
  `docs/04-structural/CODING_STANDARDS.md` §7, which sets 400. Importing them stands up a
  second competing standard — the SoT violation
  `.cursor/rules/coding-standards-mandatory.mdc` §4 forbids. Do not add them back.
- **ECC's `gh pr review --approve` publish step.** Posting to GitHub is outward-facing and
  belongs behind explicit intent; this skill also runs on plain branches with no PR.
- **ECC's verdict vocabulary.** `APPROVE / REQUEST CHANGES / BLOCK` claims merge authority.
  Step 7 says `PASS / PASS WITH COMMENTS / CHANGES NEEDED` on purpose — a verdict on a
  review, not a gate on a merge.

Use `/ecc:code-review` for an inbound GitHub PR; use this one to audit a branch against a spec.

### Process extras

- Prefer a **fresh session** (same-session review is confirmation bias).
- Diff is `<fixed-point>...HEAD` — **committed only**. Commit (or stash _own_ paths only) before reviewing WIP.
- Ask for fixed point if missing; refuse bad ref / empty diff before spawning.
- Standards sources (repo overrides smells): `docs/04-structural/CODING_STANDARDS.md`, `docs/04-structural/ARCHITECT_CHECKLIST.md`, `.cursorrules` / `AGENTS.md`, `docs/07-security/SECURITY_GUIDELINES.md`, FE/BE verify gates.
- Spec sources: issue via `docs/agents/issue-tracker.md`, user path, `docs/` / `.scratch/`, or skip Spec axis.
- Findings are hypotheses — verify citations before acting. Do **not** loop until clean (no convergence).
- Shell via `./scripts/run-with-nohup.sh`. Subagent model: Sonnet (`AGENTS.md`).
- Snyk "High Risk" on this skill is a capability-surface flag (git + subagents), not a proven exploit.
- Policy authority: `.cursorrules` / `CODING_STANDARDS.md`.
