# Coverage requirements (SoT)

**Enforced gates** use the numbers below. Per-layer targets in other docs are guidance; **CI and local verify scripts follow this file.**

## Constants

| Stack    | Minimum (enforced)                                         | Notes                                                                                                                                                                                                                                                                                          |
| -------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend  | **≥ 80%**                                                  | `coverage.py` `fail_under`; pytest `--cov-fail-under`                                                                                                                                                                                                                                          |
| Frontend | **≥ 90%** lines, functions, statements; **≥ 85%** branches | Vitest `coverage.thresholds` in `apps/web/vitest.config.mts`. Branch % lags due to optional chaining, UI guards, and chart paths; gate still blocks regressions on executable lines. Epic B (RefactorHuge) relaxed branches 86 → 85 after ~240 file renames rebalanced the baseline to 85.96%. |

### Backend details

- **Statement (line) coverage:** `[tool.coverage.run] branch = false` so the enforced percentage matches executable lines (not a blended branch headline).
- **Curated omissions** (same as always): `src/scripts/*`, Numba feature kernels (`numba_*.py`), `src/workers/**`, `src/infrastructure/ml/trainers/**`.

## Where it is wired (update all when the bar changes)

1. **Backend — canonical:** `apps/api/pyproject.toml` → `[tool.coverage.report]` → `fail_under`
2. **Backend — scripts:** `apps/api/scripts/verify.sh` → `COV_ARGS` … `--cov-fail-under=…`
3. **Backend — CI:** `.github/workflows/ci.yml` → `backend-test` → `pytest … --cov-fail-under=…`
4. **Frontend — canonical:** `apps/web/vitest.config.mts` → `test.coverage.thresholds` and `test.coverage.exclude`
5. **Frontend — CI:** `.github/workflows/ci.yml` → `frontend-test` runs `pnpm --filter @pulsai/web test:coverage` (thresholds come from Vitest config)

### Frontend unit coverage scope (Vitest)

Thresholds apply to **instrumented** files only. `coverage.exclude` omits Next.js app routes (`src/app/**`), React `src/components/**` (covered via RTL/E2E where applicable), Plotly chart glue (`src/utils/plotly-chart-helpers/**`), and barrel-only `index` re-exports — see `apps/web/vitest.config.mts`. Adjust excludes only with architecture review (same spirit as backend curated omissions).

## Docs and PR hygiene

- `docs/05-testing/TESTING_STRATEGY.md`, `docs/04-structural/CODING_STANDARDS.md`, `.github/PULL_REQUEST_TEMPLATE.md` should stay aligned with this file.

Async-heavy backend paths can make coverage tooling under-count in spots; the numeric gate still uses the curated scope above.
