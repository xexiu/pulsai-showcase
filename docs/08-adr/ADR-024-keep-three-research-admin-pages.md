# ADR-024 — Keep the three research admin pages; disambiguate by STAGE, do not merge

- **Status:** Accepted
- **Date:** 2026-08-07
- **Supersedes ticket:** ARCH-4 ("3 admin pages → 2: loop = control plane, registry = corpus + money, insights-tier = filter")

## Context

`/admin/research-loop`, `/admin/research-registry` and `/admin/insights-tier` were reported as
confusable, and a consolidation to two pages was proposed with a specific split: the loop page
becomes the control plane, the registry page becomes corpus + money, and insights-tier degrades to
a filter over the registry.

Measured before building it — the data hooks each page actually consumes:

| Page                | Data hooks                                                                                                           |
| ------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `research-loop`     | `useResearchLoopStatus` — status only                                                                                |
| `research-registry` | 8, incl. `useRunLoop`, `useRunLoopFlags`, `useSetRunLoopFlags`, `useRunHuntLoop`, `useLoopHistory`, `useLoopReadout` |
| `insights-tier`     | `useInsightsTierRegistry`                                                                                            |

## Decision

**Keep three pages. Do not merge.** The proposed split is rejected on three measured grounds.

1. **It is inverted.** The control plane already lives in `research-registry` — that page owns
   `useRunLoop`, `useRunLoopFlags`, `useSetRunLoopFlags` and `useRunHuntLoop`. The proposal would
   MOVE the control plane out of the page that has it into the page that only shows status, which
   is a real refactor of the most dangerous surface in the admin UI (it starts runs and flips
   flags) in exchange for no stated user benefit.

2. **`insights-tier` is not a filter over the registry — it is a different corpus.** It reads
   `NICE_TO_HAVE_REGISTRY.md` via `nice_to_have_registry_parser`, whose rows are book-level
   research candidates (XS cross-sectional trend book, vt-17 momentum parity, VRP OOD kill-switch,
   stablecoin overlay). `research-registry` reads `edge_hunt_models/registry.json`, whose rows are
   ML hypothesis leaves. **Not one row appears in both** (measured 2026-08-07; see ADR context in
   the `NICE_TO_HAVE_REGISTRY.md` header). Merging them puts two disjoint corpora behind one
   heading, which manufactures exactly the confusion the merge was meant to remove.

3. **The confusion was already solved, differently and correctly.** Commit `0ecdddcfd`,
   _"name the pipeline STAGE on the three confusable research pages"_, addressed this by LABELLING
   each page with the pipeline stage it represents. Merging would undo a fix that is already in
   place and working.

## Consequences

- The three pages stay. If confusion recurs, the remedy is the stage label — extend it, do not
  consolidate.
- The genuine duplication is not in the pages, it is in the **tier sources** behind them
  (`/admin/models/inventory` derives tiers from storage prefixes and knows nothing about
  `edge_hunt_model_staging.py`, the canonical contract). That is tracked as SOT-1, and its fix is
  bounded: union registry rows whose `resolve_fe_surfaces` includes `chart_overlay` into the
  inventory endpoint. It is blocked behind artifact export — 0 of 19 research rows have shippable
  weights, so bridging today would list models that fail at load.
- Fixing the pages would not have fixed the data. Fixing the data does not require touching the
  pages.

## Notes

Three of four ARCH/SOT tickets resolved this day were resolved by **verifying the premise instead
of building the ticket**: ARCH-1 (symmetry would auto-promote a book that loses money on the next
window), ARCH-3 (disjoint corpora, not a view), SOT-1 (the contract already exists and is live).
ARCH-4 is the fourth. Each would have added code that looked like progress.
