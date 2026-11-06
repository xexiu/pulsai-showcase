# ADR-021: Spec-Driven Development stance — stay Spec-Anchored (L2) + TDD, defer frameworks

## Status

**Accepted** — 2026-06-19

Records a decision only. Ships no code. Any implementation (see Success /
Validation Criteria) is a separate, TDD'd slice on a clean tree.

## Context

A survey comparing 15 spec-driven development (SDD) frameworks (Medium,
J. Wasowski) raised the question: should PulsAI adopt a named SDD framework
(Spec-Kit, MUSUBI, Superpowers, Tessl, Intent, …)?

PulsAI already runs a de-facto **L2 "Spec-Anchored"** process with mandatory
TDD and programmatic blocking gates — we just never named it:

| Framework concept          | PulsAI equivalent (already in place)                                      |
| -------------------------- | ------------------------------------------------------------------------- |
| Constitution               | `CLAUDE.md` + `AGENTS.md`                                                 |
| Pre-code hard gate         | `.claude/rules/coding-standards-mandatory.md` (Phase-0 reuse + RED-first) |
| Programmatic blocking      | `apps/api/scripts/verify.sh` / `pnpm verify` + whole-tree pre-push        |
| spec → plan → tasks → impl | `prd-to-plan` / `feature-slice-tdd` / `tdd` skills + `.cursor/plans/*`    |
| Standards / architecture   | `ARCHITECT_CHECKLIST.md`, `MODULE_MAP.md`, `DDD_PATTERNS.md`              |

Two areas are weaker than the heavyweight frameworks — but a 2026-06-20
verification found both are **already partially covered** (contrary to this
ADR's original draft):

1. **Traceability** — we already enforce code↔contract↔test parity via
   `apps/api/tests/unit/architecture/` (import-layering + feature-columns/groups
   parity invariants) and `apps/api/tests/contract/` (FE↔BE parity, golden
   contracts, `test_web_ts_alignment`). What we lack is **requirement-ID-level**
   (REQ→design→code→test) traceability of the kind MUSUBI / CSDD formalize — a
   narrower gap than "no traceability".
2. **Drift defense** — a doc-drift audit already exists
   (`.claude/plans/MASTER_DOC_DRIFTS_RANKED.md`) alongside runtime drift guards
   (`test_confidence_drift.py`, `is-deploy-version-drift.ts`). What's missing is
   an **automated, standing** doc↔code drift check, not drift awareness itself.

> **Correction (2026-06-20):** the original draft asserted "no traceability" and
> "no standing drift defense". That was under-investigated and wrong — both
> partially exist (above). The decision below is unchanged and, if anything,
> reinforced: we already have more than the draft assumed.

Caveats from the survey: its GitHub-star counts and the "73% defect reduction"
stat are **unverified** and several look inflated; **Spec-as-Source (L3, e.g.
Tessl)** is explicitly aspirational, not production-ready in 2026.

Critical distinction the survey misses: SDD pipelines fit **deterministic
feature work**, not **exploratory quant/ML research** — where the correct gate
is _hypothesis → cheapest validation_, not _spec → implement_. Forcing a spec
pipeline onto a research spike is ceremony around an experiment.

## Decision Drivers

1. Do not pay re-platforming cost for capability we already have (the survey
   measured a ~10× per-task slowdown for Spec-Kit vs baseline).
2. Close the two real gaps (traceability, drift) without adding a framework.
3. Protect research velocity — keep feature-work and research under different
   gates.
4. Do not build net-new tooling mid-session into a tree full of another dev's
   uncommitted work (entanglement / verification-isolation risk).

## Considered Options

### Option A — Stay L2 Spec-Anchored + TDD; extend existing traceability + drift (Chosen)

Keep the current process. Two narrow refinements on a clean tree, both
**extending tooling we already have** (not net-new): requirement-ID-level
traceability layered over the existing contract/architecture parity tests, and
an automated standing doc↔code drift check built on the existing
`MASTER_DOC_DRIFTS_RANKED` audit.

### Option B — Adopt a named framework (Spec-Kit / MUSUBI / Superpowers) — Rejected

Re-implements what we have at the measured per-task cost; adds a dependency and
migration burden for no capability we lack.

### Option C — Spec-as-Source / L3 (Tessl) — Rejected (for now)

Aspirational in 2026 per the survey's own author ("watching, not deploying").
Our research half of the codebase would choke on generated-from-spec workflows.
Revisit only if Tessl exits closed beta against a concrete need.

## Decision

Adopt **Option A**:

1. **Do not** adopt any named SDD framework.
2. **Do not** impulse-build traceability/drift tooling; defer behind a proper
   slice on a clean tree.
3. Keep two explicit disciplines: **L2 Spec-Anchored + mandatory TDD** for
   feature work; **hypothesis → cheapest-validation** gate for research.
4. When scheduled: add **lightweight req→test traceability on ML/financial
   correctness paths only** (triple-barrier targets, OOS guards, backtest
   accounting) and a **standing doc-drift audit** (e.g. wire the gortex
   CLAUDE.md-drift audit, `gortex://audit`, into CI / a periodic check).
5. **Reject Spec-as-Source / L3**; revisit only on a concrete future need.

## Success Criteria

- Each critical-path requirement links to **≥1 behavior test** (not just an
  implementation test); the link is **queryable/checkable**, not prose.
- A drift check flags doc↔code divergence (a referenced file/flag/function that
  no longer exists) and runs **without manual prompting**.
- **Zero** new framework dependency; per-task authoring cost on non-critical
  paths is unchanged.

## Validation Criteria

- **Traceability:** a CI/script step enumerates critical-path requirements and
  fails if any lacks a linked passing behavior test. Coverage gates unchanged
  (BE ≥ 80%, FE ≥ 90%).
- **Drift:** the audit yields zero false "missing reference" on a clean tree and
  catches a deliberately introduced stale reference (regression fixture).
- **Cost:** a routine feature-slice gate time stays within noise of today's
  baseline.

## Consequences

### Positive

- Keep the working process; close the two real gaps without ceremony.
- Research velocity protected by keeping it out of the feature-work gate.

### Negative / Trade-offs

- Traceability + drift audit are net-new work that must be **scheduled into a
  clean tree**, not built over parallel-dev WIP.
- Manual discipline remains required until the audit is automated.

### Non-goal

This ADR records a stance and ships no code. Implementation is a separate,
TDD'd slice with the Success / Validation Criteria above as its done-definition.

## References

- Survey: "Comparing 15 Spec-Driven Development Frameworks (SDD)" — J. Wasowski
  (Medium).
- `CLAUDE.md`, `AGENTS.md`, `docs/04-structural/ARCHITECT_CHECKLIST.md`,
  `docs/04-structural/CODING_STANDARDS.md`, `docs/04-structural/DDD_PATTERNS.md`.
- gortex CLAUDE.md-drift audit resource: `gortex://audit`.
- Precedent: [ADR-019](./ADR-019-ohlcv-chunk-interval.md) was likewise prompted
  by an article review.
