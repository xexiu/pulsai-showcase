/**
 * Signal + exit-strategy string constants (SoT for chart/trading UI).
 * Split from core.ts — keep sections ≤400 lines per CODING_STANDARDS.
 */

// ============================================================================
// Signal/Trading Constants
// ============================================================================

export const SIGNAL_ACTIONS = {
  BUY: 'BUY',
  SELL: 'SELL',
  HOLD: 'HOLD',
} as const;

export type SignalAction = (typeof SIGNAL_ACTIONS)[keyof typeof SIGNAL_ACTIONS];

export const SIGNAL_OUTCOMES = {
  CORRECT: 'correct',
  INCORRECT: 'incorrect',
  PENDING: 'pending',
} as const;

/**
 * Signal type for display (ML / Classic / Hybrid).
 * Used by SignalTypeBadge, notification settings, signals list.
 * WHY separate from SIGNAL_SOURCES: hybrid is a display tier (ML + Classic agreement), not a backend source.
 */
export const SIGNAL_TYPES = {
  ML: 'ml',
  CLASSIC: 'classic',
  HYBRID: 'hybrid',
} as const;

export type SignalType = (typeof SIGNAL_TYPES)[keyof typeof SIGNAL_TYPES];

/** All valid signal type values (for runtime checks and iteration). */
export const VALID_SIGNAL_TYPES: readonly SignalType[] = Object.values(SIGNAL_TYPES);

// ============================================================================
// Exit Strategy Constants
// ============================================================================

export const EXIT_STRATEGIES = {
  FIXED_HOLDING: 'fixed_holding',
  RAW_SIGNAL: 'raw_signal',
  FIXED_TPSL: 'fixed_tpsl',
  RISK_REWARD: 'risk_reward',
  TRAILING_STOP: 'trailing_stop',
  ATR_BASED: 'atr_based',
  DYNAMIC_TPSL: 'dynamic_tpsl',
  PREDICTED_REGRESSOR: 'predicted_regressor',
  MIN_PROFIT_AFTER_FEES: 'min_profit_after_fees',
} as const;
