export const BACKTEST_BUILD_TRACES_GUARD_MS = 600;

export function scaledPerfBudgetMs(baseMs: number): number {
  const raw = process.env['PULSAI_PERF_MULTIPLIER'] ?? '1';
  const parsed = Number.parseFloat(raw);
  const multiplier = Number.isFinite(parsed) ? Math.max(0.5, parsed) : 1;

  return baseMs * multiplier;
}

/**
 * Whether perf-budget assertions are *enforced* in the current run.
 *
 * WHY a gate at all:
 *   Perf budgets are wall-clock based and therefore environment-dependent.
 *   On loaded laptops, CI runners with shared hosts, and Vitest workers with
 *   spike contention the absolute numbers vary by 3-10x. Enforcing them by
 *   default produces flake without signal — the test fails because the
 *   machine was busy, not because the code regressed.
 *
 * Policy:
 *   - Default (no env): the perf test still *runs* (covers the code path)
 *     but skips the numeric assertion. Use the `expectPerfBudgetMet` helper
 *     to honor this consistently.
 *   - `PULSAI_PERF_BUDGETS=1`: enforce assertions (CI perf job, local benchmarking).
 *   - `PULSAI_PERF_MULTIPLIER=N`: scale the budget (slow machines).
 *
 * Set in `.github/workflows/ci.yml` for the perf-budget job only.
 */
export function perfBudgetsEnforced(): boolean {
  return process.env['PULSAI_PERF_BUDGETS'] === '1';
}

/**
 * Asserts `actualMs < budgetMs` only when perf budgets are enforced.
 * Otherwise logs the observed sample for diagnostic purposes.
 *
 * Reuses `scaledPerfBudgetMs` so `PULSAI_PERF_MULTIPLIER` still applies when
 * budgets are enforced on a known-slow runner.
 */
export function expectPerfBudgetMet(
  actualMs: number,
  baseBudgetMs: number,
  label: string,
  expectFn: (actual: number) => { toBeLessThan: (budget: number) => void }
): void {
  const budget = scaledPerfBudgetMs(baseBudgetMs);

  if (perfBudgetsEnforced()) {
    expectFn(actualMs).toBeLessThan(budget);

    return;
  }

  console.info(
    `[perf-budget:${label}] actual=${actualMs.toFixed(1)}ms budget=${budget.toFixed(1)}ms ` +
      '(assertion skipped; set PULSAI_PERF_BUDGETS=1 to enforce)'
  );
}
