---
name: to-spec
description: >-
  Turn the current conversation into a spec and publish it to the project issue
  tracker — no interview, just synthesis of what you've already discussed.
  User-invoked (/to-spec). Multi-session builds only.
disable-model-invocation: true
---

This skill takes the current conversation context and codebase understanding and produces a spec. Do NOT interview the user — just synthesize what you already know.

The issue tracker and triage label vocabulary should have been provided to you — see `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md` (PulsAI). Run `/setup-matt-pocock-skills` only if those are missing.

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout the spec, and respect any ADRs in the area you're touching.

2. Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. The fewer seams across the codebase, the better - the ideal number is one.

Check with the user that these seams match their expectations.

3. Write the spec using the template below, then publish it to the project issue tracker. Apply the `ready-for-agent` triage label - no need for additional triage.

<spec-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this spec.

## Further Notes

Any further notes about the feature.

</spec-template>

## PulsAI usage (mandatory)

Guide: [aihero](https://www.aihero.dev/skills-to-spec).

### When / when not

| Situation                                                              | Move                                                                    |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Decisions already made; work **spans several sessions**                | `/to-spec` (this skill) → then `/to-tickets` or PulsAI `/prd-to-issues` |
| Cleared `/wayfinder` map                                               | `/to-spec #<map_issue>` — collapse the **map** issue, not each child    |
| Decided; fits **one** context window                                   | Skip — `/implement` or `/tdd`                                           |
| Nothing decided yet                                                    | `/grill-me` / `/grill-with-docs` / `/wayfinder` first                   |
| Want a **local** plan with contract blocks, not a tracker parent issue | PulsAI `/prd-to-plan` (sibling; often enough)                           |

**Record, do not decide.** Anything the spec asserts that the owner never said is a defect. Prefer empty sections over invented filler.

### Seams before prose (hard)

1. Propose **as few seams as possible** (prefer one; prefer existing).
2. **Wait for owner confirmation** before writing the issue body.
3. Those seams travel into `/tdd` and `/code-review` — a seam nobody agreed is a review finding.

### Tracker publish (PulsAI)

- Config: `docs/agents/issue-tracker.md` + `docs/agents/triage-labels.md`.
- Create with `gh issue create` via `./scripts/run-with-nohup.sh`. Apply `ready-for-agent`.
- ADRs you respect live under `docs/08-adr/` — do **not** invent `docs/adr/`. Do not invent ADR links the conversation never named.
- Search the tracker yourself for overlapping work before filing (skill does not).

### `ready-for-agent` on the **parent** spec (AFK pitfall)

The label means “complete enough to work from,” **not** “build this whole issue in one AFK run.” After `/to-tickets` (or `/prd-to-issues`) cuts children, either:

- Exclude the parent spec issue from AFK/`ready-for-agent` pollers, **or**
- Strip `ready-for-agent` from the parent once children exist.

Children carry execution; the parent is the durable decision record.

### Hard rules

- **User-invoked only** — do not auto-run at session start.
- No fresh interview round; synthesize thread + codebase + glossary/ADRs.
- Out-of-scope must list real refusals from the conversation.
- Shell: `./scripts/run-with-nohup.sh`. Subagents (if any): Sonnet.
- Policy: `.cursorrules` / `CODING_STANDARDS.md` / `AGENTS.md`.
- Downstream: `/to-tickets` (same context window when possible) or PulsAI `/prd-to-issues` / `/prd-to-plan`. Then `/implement` per child — never implement the parent spec as one blob.
