/**
 * Risk labels, timeframes, numeric thresholds, debounce, validation, display limits.
 * Split from core.ts — keep sections ≤400 lines per CODING_STANDARDS.
 */

// ============================================================================
// Risk/Audit Constants
// ============================================================================

export const RISK_LEVELS = {
  CRITICAL: 'critical',
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
} as const;
// ============================================================================
// Time/Exchange Constants
// ============================================================================

export const TIMEFRAMES = {
  M5: '5m',
  M15: '15m',
  H1: '1h',
  H4: '4h',
  D1: '1d',
} as const;

export type Timeframe = (typeof TIMEFRAMES)[keyof typeof TIMEFRAMES];

// EXCHANGES / Exchange — removed. Canonical SoT is ``EXCHANGE_IDS`` /
// ``ExchangeId`` in ``@pulsai/shared`` (covers all 6 venues, not the
// 2-element legacy subset). ``LIVE_EXCHANGE_IDS`` in
// ``@/lib/live-exchange/types`` provides the object-keyed access pattern
// (``LIVE_EXCHANGE_IDS.BINANCE``) for sites that need it.

// ============================================================================
// Trading Thresholds
// ============================================================================

export const TRADING_THRESHOLDS = {
  PROFIT_FACTOR_GOOD: 1.5,
  /** Break-even profit factor; below this a strategy is net-losing. Promote soft-gate floor (mirrors BE MODEL_PROMOTE_MIN_PROFIT_FACTOR). */
  PROFIT_FACTOR_BREAKEVEN: 1.0,
  WIN_RATE_GOOD: 0.5,
  CONFIDENCE_HIGH: 0.7,
  CONFIDENCE_MEDIUM: 0.5,
  IC_ACCEPTABLE: 0.05,
} as const;

// ============================================================================
// Numeric Scales
// ============================================================================

/** Multiplier for converting 0-1 ratios to 0-100 percentages (display). */
export const PERCENTAGE_SCALE = 100 as const;

// ============================================================================
// Time Constants
// ============================================================================

export const TIME_MS = {
  SECOND: 1000,
  MINUTE: 60000,
  HOUR: 3600000,
  DAY: 86400000,
} as const;

export const DEBOUNCE_MS = {
  SEARCH: 300,
  FAST: 50,
  NOTIFICATION: 3000,
  NAVIGATION_TIMEOUT: 5000,
  ADMIN_MESSAGE_CLEAR: 5000,
} as const;

// ============================================================================
// Validation Constants
// ============================================================================

export const VALIDATION = {
  MIN_NAME_LENGTH: 2,
  /** Matches backend invitation / VIP code field max length. */
  INVITATION_CODE_MAX_LENGTH: 64,
} as const;

// ============================================================================
// Display Limits
// ============================================================================

export const DISPLAY_LIMITS = {
  TRADES_TABLE: 50,
  TRUNCATE_SHORT: 8,
  TRUNCATE_MEDIUM: 50,
  TRIAL_LOGS: 10,
} as const;
