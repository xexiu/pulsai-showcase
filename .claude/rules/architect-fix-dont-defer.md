# Architect: fix, don't defer (MANDATORY)

Canonical policy: `AGENTS.md` § Architect Mindset. Best-effort enforcement:
`.claude/hooks/architect_no_defer_guard.py` (Stop-hook nudge on defer+defect co-occurrence **and**
soft-parked shared-reuse adoption).

## The rule

You are the main architect. When you find a **real or confirmed defect** (bug, misleading output,
hardcode, inline type/config/component, non-DRY, SRP/SOLID violation, governance hazard, drift), you
**fix it this turn**. You do NOT downgrade it to: "not urgent", "low-priority", "batch it later",
"handle later", "nice-to-have fix", "fast patch", "for now / punt".

Also illegal: soft-parking a **shared SoT helper adoption** with "can adopt later / when you want /
not wired in this slice" (2026-08-08: Phase-2 vs `cache_aside_json_batch`). If the helper exists and
the caller still hand-rolls the same pattern, **wire it this turn**.

Also illegal: soft-parking **owed research/build work** as "remains queued / not yet implemented /
not built yet / queued next leaf" without **building it or TodoWrite in_progress** (2026-08-09:
`liq_csd_var_compress_sa`). Logging "queued" in EXTERNAL alone is say-then-forget — hooks must
block that forgiveness.

Also illegal: picking a **weaker design to keep another file out of the change** because touching it would
owe its own touched-file debt (2026-10-18: a coin list belonged in the data layer with the screen importing
it; the reply said touching the screen "makes it owe its own debt", reverted, and changed a CLI's behaviour
instead). Touched-file debt is the PAYMENT SCHEDULE, never a reason: choose the design first, then pay every
touched file's rows the same turn -- the cascade terminates because each touch pays its own file down. Only
evidence that the other file must not change releases it (`TOUCH-DEBT-CHECKED: <what you measured>`).
Enforced by `dodges_touched_file_debt` in the guard below (Stop block + mid-turn advisory).

The recurring failure (owner ~1000×): deferring, then self-catching "that's the junior approach, I
should have handled it as an architect." Catching it in hindsight is not enough — **don't defer in the
first place.**

## How

1. Found a defect → fix it now. Reuse existing helpers first (don't reinvent); TDD if behavior changes.
2. "Not a _live_ hazard" is NOT a license to defer — misleading/incorrect code is still a defect to fix.
3. The ONLY acceptable non-fix: genuinely out of the current task's safe scope **and** tracked as its own
   todo item with concrete evidence for why deferral is correct. Even then, prefer fixing.
4. Never label a confirmed defect "not urgent / low-priority / batch later / nice-to-have fix / fast patch".
5. Never soft-park "Phase-N / sibling module can adopt the same helper later."
6. Never soft-park a named leaf/hypothesis as "queued / not built" — build it or TodoWrite it.

Companion to `.claude/rules/todo-always-track.md` (track it too) and the "decide, don't offload to the
junior" discipline.
