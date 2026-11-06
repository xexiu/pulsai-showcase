# ADR-020: Frontend table stack — custom vs TanStack Table v9

## Status

**Accepted** — 2026-06-18

Defer `@tanstack/react-table` adoption; **custom table stack remains source of truth** for `apps/web`.

Companion implementation detail (spike protocol, code paths): [TABLE_STACK_CUSTOM_VS_TANSTACK_TABLE_V9.md](../02-technical/TABLE_STACK_CUSTOM_VS_TANSTACK_TABLE_V9.md).

## Context

PulsAI `apps/web` uses **TanStack Query** for server state but **does not** depend on `@tanstack/react-table`. List and admin UX is built from:

| Building block                 | Role                                                               |
| ------------------------------ | ------------------------------------------------------------------ |
| `useTableQueryState`           | Page + sort state for URL/API-driven lists                         |
| `SortableHeaderCell`           | Header click → sort column/direction                               |
| `PaginatedHistoryTable`        | Generic paginated `<table>` shell                                  |
| Admin / audit / signals tables | Server-side sort + pagination via API                              |
| `MultiMetricsTable`            | Client-side sort + per-metric highlighting (explicitly no library) |

TanStack Table **v9** (2026) introduces modular features, tree-shakeable runtime, per-table typed `sortFn` / `filterFn` / meta, and improved TypeScript performance vs early v9 alphas (~2× v8 type cost at beta vs ~14.7× at worst alpha). See [TypeScript Performance in TanStack Table V9](https://tanstack.com/blog/tanstack-table-v9-typescript-performance).

Most PulsAI tables are read-only, **API-paginated** lists — not spreadsheet-grade client grids.

## Decision Drivers

1. **Simplicity first** — avoid dependencies without a forcing function ([CODING_STANDARDS.md](../04-structural/CODING_STANDARDS.md), `.cursorrules`).
2. **Server-side sort** — admin/audit/subscriptions/signals already sort via API + `useTableQueryState`.
3. **Zero current Table usage** — adoption is greenfield cost, not migration savings.
4. **Beta timing** — v9 is not stable as of Jun 2026; [DEPENDENCY_POLICY.md](../02-technical/DEPENDENCY_POLICY.md) favors proven deps on core UI paths.
5. **Ecosystem alignment** — TanStack Query is standard; Table can join later without rewriting Query layers.

## Considered Options

### Option A — Keep custom stack; defer TanStack Table v9 (Chosen)

Continue `SortableHeaderCell` + `useTableQueryState` + thin `<table>` molecules. Re-evaluate v9 **per feature slice** only after stable release and when an adoption gate clears (≥2 triggers — see companion doc).

Policy:

> **TanStack Query: standard. TanStack Table v9: opt-in per complex grid, not a default dependency.**

### Option B — Adopt TanStack Table v9 repo-wide now — Rejected

Adds bundle + API surface + beta risk with no user-visible gain on existing server-sorted admin lists. V9 is a redesign, not a drop-in bump.

### Option C — Adopt TanStack Table v8 — Rejected

V8 global declaration merging and non-tree-shakeable feature model are the problems v9 fixes. Adopting v8 now would invite a second migration soon.

## Decision

Adopt **Option A**.

Do **not** add `@tanstack/react-table` to `apps/web/package.json` until a spike PR explicitly clears the adoption gate and v9 is **stable**.

## Adoption gate (re-open this ADR when evaluating a slice)

Adopt TanStack Table v9 for a **specific screen** when **at least two** apply:

- Column resize, reorder, pin, or visibility toggles
- Row selection + bulk actions on large client-held sets
- Client-side filtering / grouping / faceting on large in-memory datasets
- Virtualized rows (10k+) with complex cells
- Multiple new screens would duplicate the same headless-table wiring

**Do not adopt** to replace working server-sorted admin tables or simple ranking tables (`MultiMetricsTable`-class).

Spike protocol before merge: branch spike → measure type-check/bundle/DX → single organism wrapper → `pnpm verify` → update this ADR revision log.

## Consequences

### Positive

- No new dependency or beta API churn on the critical admin/trading UI path.
- Custom stack stays small, testable, and aligned with server-driven pagination.
- Clear gate prevents newsletter-driven dependency adds.

### Negative / Trade-offs

- Complex future grids (column pin, bulk select, client faceting) require either hand-rolling more logic or a later v9 spike.
- If v9 becomes industry default, we may adopt later with a focused wrapper organism rather than incremental creep.

### Agents / implementers

Before proposing `@tanstack/react-table` on a task, read this ADR and the companion doc. Default implementation path is custom stack.

## References

- Companion: [TABLE_STACK_CUSTOM_VS_TANSTACK_TABLE_V9.md](../02-technical/TABLE_STACK_CUSTOM_VS_TANSTACK_TABLE_V9.md)
- Code: `apps/web/src/hooks/useTableQueryState.ts`, `apps/web/src/components/atoms/SortableHeaderCell/`, `apps/web/src/components/molecules/PaginatedHistoryTable/`, `apps/web/src/components/molecules/IndicatorBenchmark/MultiMetricsTable.tsx`
- TanStack: [v9 TypeScript performance](https://tanstack.com/blog/tanstack-table-v9-typescript-performance), [v9 product overview](https://tanstack.com/blog/tanstack-table-v9-taking-form)
- [TECH_STACK.md](../02-technical/TECH_STACK.md) (TanStack Query)
- FE_STATE_MAP.md

## Revision log

| Date       | Change                                              |
| ---------- | --------------------------------------------------- |
| 2026-06-18 | Accepted: defer v9; custom stack SoT; adoption gate |
