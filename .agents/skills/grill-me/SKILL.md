---
name: grill-me
description: Interview the user to resolve design ambiguity before implementation. Use when a feature has trade-offs, unclear requirements, or architecture decisions across frontend/backend.
---

# Grill Me (PulsAI)

## Goal

Force design clarity before code. Ask targeted questions until requirements, constraints, risks, and test strategy are explicit.

## Required Workflow

1. Confirm scope, constraints, and success criteria.
2. Build a design tree: decisions, alternatives, and dependencies.
3. For each decision, ask one sharp question at a time.
4. When answer can be found in repo/docs, inspect first and ask only unresolved questions.
5. End only when the execution path is unambiguous.

## Mandatory Outputs

- Final decision log (chosen option + rejected alternatives + why)
- Risks and mitigations
- FE/BE impact map
- Test strategy (behavior tests + regression tests)
- Verification plan:
  - `cd apps/api && ./scripts/verify.sh`
  - `cd apps/web && pnpm verify`

## PulsAI Guardrails

- `.cursorrules` and `docs/04-structural/CODING_STANDARDS.md` are source of truth.
- Prefer explicit logic over compact clever code.
- Enforce TDD mindset and behavior-first testing.
- When a domain term resolves, also run `/domain-modeling` so `CONTEXT.md` updates inline (glossary only). Do not leave grilling with a settled word that never hit the glossary.
- If the effort clearly won't fit one session, stop and offer `/wayfinder` instead of pretending a single grill can hold the whole map.
- Want glossary/ADR writes during the interview → `/grill-with-docs` instead (loads `/grilling` + `/domain-modeling`).
