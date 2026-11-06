---
name: improve-codebase-architecture
description: Identify architecture improvements that reduce coupling, improve testability, and simplify module boundaries. Use during periodic architecture hygiene or after major feature bursts.
---

# Improve Codebase Architecture (PulsAI)

## Goal

Continuously improve maintainability, testability, and clarity without destabilizing behavior.

## Required Workflow

1. Inspect current module boundaries and dependency directions.
2. Identify high-risk coupling and shallow abstractions.
   2b. Before proposing ANY pattern, check it against
   `docs/04-structural/ARCHITECTURE_PATTERNS.md` — specifically its **anti-fit** column and §9
   anti-patterns (golden hammer, over-abstraction, premature distribution, unobservable
   resilience). A proposal must name the failure the pattern prevents; "cleaner" is not a reason.
   Adding a resilience pattern (retry / circuit breaker / bulkhead) without saying what emits and
   who reads it is forbidden — it converts a loud failure into a silent one.
3. Propose targeted improvements with migration-safe sequence.
4. Define regression and performance checks for each change.
5. Execute changes incrementally with verification gates.

## Required Output

- Ranked findings (severity + impact)
- Proposed refactor slices (small, reversible)
- Test strategy for each slice
- Performance and security considerations
- Verification commands:
  - `cd apps/api && ./scripts/verify.sh`
  - `cd apps/web && pnpm verify`

## PulsAI Guardrails

- Do not introduce large-bang refactors.
- Prefer explicit modules with clear responsibilities (SRP/DIP).
- Keep `.cursorrules` and coding standards as policy authority.
- When arguing module **shape**, use `/codebase-design` vocabulary (seam / interface / depth); this skill owns the survey + slices, not the glossary.
- When domain **words** crystallise, invoke `/domain-modeling` so `CONTEXT.md` updates inline (glossary only; ADRs → `docs/08-adr/`).
