---
name: tdd
description: Execute strict red-green-refactor for behavior changes. Use when implementing features, bug fixes, or regressions requiring tests-first development.
---

# TDD (PulsAI)

## Goal

Implement changes with tests first, one vertical slice at a time.

## Required Loop

1. Define behavior outcome for the next tiny slice.
2. Write failing test first (RED).
3. Implement minimum code to pass (GREEN).
4. Refactor safely without changing behavior (REFACTOR).
5. Repeat until slice is complete.

## Test Quality Rules

- Test behavior, not implementation details.
- Include edge cases and regression scenario.
- Keep tests fast; mock network/external systems.
- If tests and code disagree, evaluate which logic is correct before changing either.

## Exit Criteria (Mandatory)

- Relevant tests pass.
- No regressions on touched flows.
- When driven by `/implement`, also satisfy that skill's verify + interim-commit-before-`/code-review` beats (see `.agents/skills/implement/SKILL.md`).
- Verification gates pass:
  - `cd apps/api && ./scripts/verify.sh`
  - `cd apps/web && pnpm verify`

## Required References (read first)

- `docs/04-structural/ARCHITECTURE_PATTERNS.md` — which pattern fits, and its
  **ANTI-FIT**, which is the half that matters. A slice that introduces a pattern must
  name the failure that pattern prevents; "cleaner" is not a reason.
- `docs/04-structural/DDD_PATTERNS.md` — where DDD applies, and where it is overkill.
- `.cursor/rules/coding-standards-mandatory.mdc` — Phase 0 reuse, SoT, SRP/SOLID.

## PulsAI Guardrails

- Reuse existing code first (no wheel reinvention).
- Keep code explicit (avoid nested ternary chains).
- Follow SRP/DRY and project coding standards.
