---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when the user wants to pin down domain terminology or a ubiquitous language, record an architectural decision, or when another skill needs to maintain the domain model.
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the _active_ discipline — challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise. (Merely _reading_ `CONTEXT.md` for vocabulary is not this skill — that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

## File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives:

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

Create files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If no `docs/adr/` exists, create it when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture them as they happen. Use the format in [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).

## PulsAI usage (mandatory)

Guide: [aihero](https://www.aihero.dev/skills-domain-modeling). Sibling vocabulary: `/codebase-design` (module _shape_); this skill is domain _words_.

### Artifacts

| Artifact            | PulsAI location                                                                                              | Rule                                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| Glossary            | Repo-root `CONTEXT.md` (create lazily on first resolved term)                                                | **Glossary only** — no specs, scratch pads, or implementation dumps (most-reported failure mode) |
| ADRs                | **`docs/08-adr/ADR-NNN-slug.md`** (house SoT; also see `docs/04-structural/adr/` for older structural notes) | Do **not** create `docs/adr/` — that path is not PulsAI convention                               |
| Map (multi-context) | `CONTEXT-MAP.md` only if two lean domains truly need a split                                                 | Never split a bloated glossary — slim first                                                      |

### Behaviour

- Write glossary entries **inline** when a term resolves; do not batch a dump at session end.
- Prefer `/grill-me` (PulsAI) as the driver; invoke `/domain-modeling` **by name** alongside grilling if `CONTEXT.md` would otherwise stay untouched (auto-load is weak).
- `/wait-what` re-pitches using `CONTEXT.md` when present; until then fall back to `AGENTS.md` / `MODULE_MAP.md`.
- Do **not** scaffold an empty `CONTEXT.md` or speculative ADRs at session start.
- ADR bar unchanged (hard to reverse ∧ surprising ∧ real trade-off). Numbering: next free `ADR-NNN` under `docs/08-adr/`.
- Policy authority: `.cursorrules` / `CODING_STANDARDS.md` win on conflict.
