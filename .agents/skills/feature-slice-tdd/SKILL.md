---
name: feature-slice-tdd
description: 'Plan and implement a feature slice using TDD and red-green-refactor. Use for tests-first behavior changes, bug fixes, contract updates, and incremental delivery with verification gates.'
argument-hint: 'Describe the feature slice, target files, behavior change, and acceptance criteria.'
user-invocable: true
---

# Feature Slice TDD

Use this workflow when implementing or fixing behavior that must be validated with tests.

## When to Use

- New behavior in backend or frontend
- Bug fix with regression risk
- API contract or validation change
- Incremental feature delivery by slices

## Procedure

1. Clarify slice scope and acceptance criteria.
2. Identify existing code to reuse before adding abstractions.
3. Write or update failing tests first (behavior-first).
4. Implement the minimal change to satisfy tests.
5. Refactor for clarity without changing behavior.
6. Run verification gates:
   - `cd apps/web && pnpm verify`
   - `cd apps/api && ./scripts/verify.sh`
7. Summarize outcomes, risks, and follow-up tasks.

## Output Format

1. Slice definition
2. Tests added/updated
3. Implementation summary
4. Verification results
5. Remaining risks
