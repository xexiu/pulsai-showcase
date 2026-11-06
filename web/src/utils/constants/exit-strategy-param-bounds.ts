/**
 * UI bounds for exit-strategy NumberInputs (min / max / step / placeholders).
 *
 * WHY separate from BACKTEST_DEFAULTS:
 * - BACKTEST_DEFAULTS = product defaults sent to the API
 * - These = input validation ranges (may match BE limits; FE is the UX guardrail)
 *
 * SoT for duplicated JSX in BacktestConfigForm vs BacktestCompare — import here only.
 */

export const EXIT_STRATEGY_PARAM_BOUNDS = {
  stopLossPct: { min: 0.1, max: 50, step: 0.1, placeholder: '2.0' },
  takeProfitPct: { min: 0.1, max: 100, step: 0.1, placeholder: '4.0' },
  riskRewardRatio: { min: 0.5, max: 10, step: 0.1 },
  trailActivationPct: { min: 0, max: 20, step: 0.1 },
  trailPct: { min: 0.1, max: 10, step: 0.1 },
  atrPeriod: { min: 5, max: 50, step: 1 },
  atrMultiplier: { min: 0.5, max: 5, step: 0.1 },
  maxSlPct: { min: 0.5, max: 20, step: 0.5, placeholder: '—' },
  minNetPct: { min: 0, max: 10, step: 0.1, placeholder: '0' },
} as const;
