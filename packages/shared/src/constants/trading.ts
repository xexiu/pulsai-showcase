// =============================================================================
// Trading Constants - Centralized configuration for symbols and timeframes
// =============================================================================
//
// WHY CENTRALIZE?
// - Single source of truth for all trading-related options
// - When backend config API is ready, only change here
// - Prevents hardcoding in 12+ frontend components
//
// TODO: Fetch from backend config API when implemented
// @see docs/02-technical/API_SPECIFICATION.md

import type { Timeframe, TradingSymbol } from '../types/common';
import { DEFAULT_SUPPORTED_SYMBOLS } from './symbol-registry';
import {
  DEFAULT_SUPPORTED_TIMEFRAMES,
  TIMEFRAME_LABELS,
  TIMEFRAME_REGISTRY_MS,
  registryTimeframeToMinutes,
  type RegistryTimeframe,
} from './timeframe-registry';

/**
 * Option format for select/dropdown components.
 * Consistent structure used across frontend.
 */
export interface SelectOption<T = string> {
  value: T;
  label: string;
}

// =============================================================================
// Symbol Configuration
// =============================================================================

/**
 * Currently supported trading symbols (fallback when /config/public is unavailable).
 * Order matters - BTC/USDT is the default.
 * Derived from the symbol registry: this was a hand-kept list of 3 while the backend served 5.
 */
export const TRADING_SYMBOLS: TradingSymbol[] = [...DEFAULT_SUPPORTED_SYMBOLS];

/**
 * Default symbol for new users/sessions.
 */
export const DEFAULT_SYMBOL: TradingSymbol = 'BTC/USDT';

/**
 * Symbol options formatted for Select components.
 */
export const SYMBOL_OPTIONS: SelectOption<TradingSymbol>[] = TRADING_SYMBOLS.map((symbol) => ({
  value: symbol,
  label: symbol,
}));

// =============================================================================
// Timeframe Configuration
// =============================================================================

/**
 * Timeframes with human-readable labels.
 * Order: shortest to longest (derived from BE registry ms).
 */
export const TIMEFRAME_CONFIG: Array<{ value: Timeframe; label: string; minutes: number }> = (
  Object.keys(TIMEFRAME_REGISTRY_MS) as RegistryTimeframe[]
)
  .map((value) => ({
    value: value as Timeframe,
    label: TIMEFRAME_LABELS[value],
    minutes: registryTimeframeToMinutes(value),
  }))
  .sort((a, b) => a.minutes - b.minutes);

/**
 * Currently enabled timeframes for the UI.
 * Mirrors BE `DEFAULT_SUPPORTED_TIMEFRAME_VALUES` (deployment filter).
 */
export const ENABLED_TIMEFRAMES: Timeframe[] = [...DEFAULT_SUPPORTED_TIMEFRAMES];

/**
 * Default timeframe for charts and training.
 */
export const DEFAULT_TIMEFRAME: Timeframe = '1h';

/**
 * Minimum confidence for ML BUY/SELL vs HOLD (percent 0–100).
 * SoT: align with BE `DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT` and
 * GET /api/v1/config/public → `limits.min_signal_confidence_percent`.
 */
export const MIN_SIGNAL_CONFIDENCE_PERCENT = 50 as const;

/**
 * Timeframe options formatted for Select components.
 * Only includes enabled timeframes with LONG labels (e.g., "1 Hour").
 */
export const TIMEFRAME_OPTIONS: SelectOption<Timeframe>[] = TIMEFRAME_CONFIG.filter((tf) =>
  ENABLED_TIMEFRAMES.includes(tf.value)
).map((tf) => ({
  value: tf.value,
  label: tf.label,
}));

/**
 * Timeframe options with SHORT labels (e.g., "1h").
 * Use for compact filters, badges, etc.
 */
export const TIMEFRAME_OPTIONS_SHORT: SelectOption<Timeframe>[] = TIMEFRAME_CONFIG.filter((tf) =>
  ENABLED_TIMEFRAMES.includes(tf.value)
).map((tf) => ({
  value: tf.value,
  label: tf.value, // Use value as label (e.g., "1h")
}));

/**
 * All timeframe options (including disabled ones).
 * Use TIMEFRAME_OPTIONS for UI components.
 */
export const ALL_TIMEFRAME_OPTIONS: SelectOption<Timeframe>[] = TIMEFRAME_CONFIG.map((tf) => ({
  value: tf.value,
  label: tf.label,
}));

// =============================================================================
// Timeframe Utilities (Sprint 2.2 - Multi-TF Support)
// =============================================================================

/**
 * Get the minutes value for a timeframe from centralized config.
 *
 * @param tf - Timeframe string (e.g., "1h", "4h")
 * @returns Minutes value, or -1 if not found
 */
export function getTimeframeMinutes(tf: string): number {
  const config = TIMEFRAME_CONFIG.find((c) => c.value === tf);

  return config?.minutes ?? -1;
}

// -----------------------------------------------------------------------------
// Chart (LWC) bar time encoding — SoT for timeToTz vs raw UTC
// -----------------------------------------------------------------------------
//
// Short bars: legacy path applies timeToTz("local wall as UTC") so the intraday
// UTC axis formatter lines up. Coarse bars (4h+): that transform breaks uniform
// x-spacing (DST + large step) → visible gaps. Use raw UTC seconds instead.
//
// When adding a timeframe: add it to TIMEFRAME_CONFIG.minutes; this threshold
// picks raw UTC automatically for minutes >= 240 (e.g. 4h, 6h, 1d). New TFs
// strictly between 1h and 4h (e.g. 2h) need a product decision if spacing breaks.
// -----------------------------------------------------------------------------

/**
 * Minimum bar period (minutes) for **raw UTC** candle times on the chart.
 * Periods **strictly below** this use legacy `timeToTz` before LWC `setData`.
 *
 * SoT: one threshold for FE (`shouldChartBarTimesUseLegacyTimeToTz`) and docs;
 * not duplicated in `timeToTz` (that function stays a pure transform).
 */
export const CHART_BAR_RAW_UTC_MIN_MINUTES = 4 * 60;

/**
 * Whether chart OHLCV `time` should use the legacy `timeToTz(utc, userTz)` mapping
 * before lightweight-charts. When false, pass Unix seconds as UTC (axis uses real timezone).
 *
 * @param timeframe - Chart TF (e.g. `1h`, `4h`). Unknown / empty → legacy (safe default).
 */
export function shouldChartBarTimesUseLegacyTimeToTz(timeframe: string | undefined): boolean {
  if (timeframe == null || timeframe === '') {
    return true;
  }
  const minutes = getTimeframeMinutes(timeframe);

  if (minutes < 0) {
    return true;
  }

  return minutes < CHART_BAR_RAW_UTC_MIN_MINUTES;
}

/**
 * Check if timeframe A is higher (longer) than timeframe B.
 * Uses centralized TIMEFRAME_CONFIG for ordering.
 *
 * @example
 * isHigherTimeframe('4h', '1h') // true (240 > 60)
 * isHigherTimeframe('15m', '1h') // false (15 < 60)
 */
export function isHigherTimeframe(tfA: string, tfB: string): boolean {
  const minutesA = getTimeframeMinutes(tfA);
  const minutesB = getTimeframeMinutes(tfB);

  // If either not found, can't compare
  if (minutesA === -1 || minutesB === -1) return false;

  return minutesA > minutesB;
}

/**
 * Get timeframes higher than the reference from a list.
 * Sorted by minutes (shortest first among higher TFs).
 *
 * WHY THIS HELPER?
 * - Centralizes timeframe comparison logic
 * - Uses TIMEFRAME_CONFIG as single source of truth
 * - Prevents hardcoded hierarchies across codebase
 *
 * @param referenceTf - Current timeframe (e.g., "1h")
 * @param timeframes - List of timeframes to filter (e.g., enabled TFs)
 * @returns Timeframes higher than reference, sorted by minutes
 *
 * @example
 * getHigherTimeframes('1h', ['15m', '1h', '4h', '1d'])
 * // Returns: ['4h', '1d']
 */
export function getHigherTimeframes(referenceTf: string, timeframes: string[]): string[] {
  const refMinutes = getTimeframeMinutes(referenceTf);

  if (refMinutes === -1) return [];

  return timeframes
    .filter((tf) => {
      const tfMinutes = getTimeframeMinutes(tf);

      return tfMinutes > refMinutes;
    })
    .sort((a, b) => getTimeframeMinutes(a) - getTimeframeMinutes(b));
}

// =============================================================================
// Training Configuration
// =============================================================================
//
// ⚠️ IMPORTANT: ALL VALUES BELOW ARE FALLBACK ONLY!
//
// Primary source of truth: Backend GET /api/v1/config/public
// Frontend should use: useAppConfig() hook → config.training.*
//
// These constants exist for:
// 1. TypeScript type definitions (type safety)
// 2. Fallback when backend is unavailable
// 3. Default values in error scenarios
//
// Adding new options? Update BACKEND config.py ONLY!
// Frontend will automatically pick up changes from /config/public
//
// @see apps/api/src/api/v1/endpoints/config.py
// @see apps/web/src/hooks/useAppConfig.ts
// =============================================================================

/**
 * Training window options (days of historical data).
 * Fallback — prefer config.training.training_window_options from useAppConfig().
 */
export const TRAINING_WINDOW_OPTIONS: SelectOption<number>[] = [
  { value: 60, label: '60 days (Fast adaptation)' },
  { value: 90, label: '90 days (Quick experiments)' },
  { value: 180, label: '180 days (Balanced)' },
  { value: 365, label: '365 days (Full market cycle)' },
];

/**
 * Default training window.
 * Fallback — prefer config.training.default_training_window from useAppConfig().
 */
export const DEFAULT_TRAINING_WINDOW = 365;

/**
 * Optimization mode options.
 */
export type OptimizationMode = 'fast' | 'standard' | 'thorough';

/**
 * Fallback — prefer config.training.optimization_mode_options from useAppConfig().
 */
export const OPTIMIZATION_MODE_OPTIONS: SelectOption<OptimizationMode>[] = [
  { value: 'fast', label: 'Fast' },
  { value: 'standard', label: 'Standard' },
  { value: 'thorough', label: 'Thorough' },
];

/**
 * Default optimization mode.
 * Fallback — prefer config.training.default_optimization_mode from useAppConfig().
 */
export const DEFAULT_OPTIMIZATION_MODE: OptimizationMode = 'standard';

// =============================================================================
// ML Model Types (Sprint 2.0b → 2.0m Refactored)
// =============================================================================

/**
 * Available ML model types - ARCHITECTURE ONLY (Sprint 2.0m refactor).
 *
 * REFACTORED:
 * - Previously: 'xgboost_2class_buy', 'xgboost_2class_sell' (direction in type name)
 * - Now: 'xgboost_2class' + separate direction field ('buy' | 'sell')
 *
 * WHY?
 * - Cleaner UI: User picks architecture first, then direction
 * - No confusing "XGBoost 2-Class (BUY vs NOT-BUY)" labels
 * - Direction is a separate concept from model architecture
 *
 * Backend resolves: model_type + direction → internal model type
 * Example: 'xgboost_2class' + 'buy' → 'xgboost_2class_buy'
 */
export type MLModelType =
  | 'xgboost_3class' // 3-class: outputs BUY/HOLD/SELL
  | 'xgboost_2class' // 2-class: binary, direction determines what to detect
  | 'lightgbm' // LightGBM: leaf-wise GBDT (Sprint 2.8)
  | 'random_forest' // Random Forest: bagging ensemble (Sprint 2.8)
  | 'catboost' // CatBoost: ordered boosting, symmetric trees (Sprint 2.12)
  | 'stacking' // Stacking: XGB+LGB+CB → LogReg meta-learner (Sprint 2.12)
  | 'voting_ensemble' // Voting ensemble of multiple models
  | 'xgboost_regression' // Regression: predict return % (Sprint 2.9b)
  | 'lightgbm_regression'; // Regression: predict return % (Sprint 2.9b)

/**
 * Model direction for binary (2-class) models.
 * - 'buy': Detect bottom/buy opportunities (model outputs: BUY or NOT-BUY)
 * - 'sell': Detect top/sell opportunities (model outputs: SELL or NOT-SELL)
 * - 'both': Used for 3-class models (outputs BUY/HOLD/SELL)
 */
export type ModelDirection = 'buy' | 'sell' | 'both';

/**
 * Fallback — prefer config.training.model_type_options from useAppConfig().
 */
export const ML_MODEL_TYPE_OPTIONS: SelectOption<MLModelType>[] = [
  { value: 'xgboost_3class', label: 'XGBoost 3-Class' },
  { value: 'xgboost_2class', label: 'XGBoost 2-Class' },
  { value: 'lightgbm', label: 'LightGBM' },
  { value: 'random_forest', label: 'Random Forest' },
  { value: 'catboost', label: 'CatBoost' },
  { value: 'xgboost_regression', label: 'XGBoost Regression' },
  { value: 'lightgbm_regression', label: 'LightGBM Regression' },
  // NOTE (Sprint 2.9): stacking and voting_ensemble excluded from training form.
  // Stacking is a meta-learner (wraps trained base models, no Optuna trainer).
  // VotingEnsemble is a combiner. Both configured via Admin Ensemble Config UI.
];

/**
 * Model direction options for Select components.
 * Fallback — prefer config.training.model_type_directions from useAppConfig().
 */
export const MODEL_DIRECTION_OPTIONS: SelectOption<ModelDirection>[] = [
  { value: 'buy', label: 'BUY Detection (Bottoms)' },
  { value: 'sell', label: 'SELL Detection (Tops)' },
  { value: 'both', label: 'Both (3-Class BUY/HOLD/SELL)' },
];

/**
 * Fallback — prefer config.training.model_types[0] or default from backend.
 */
export const DEFAULT_ML_MODEL_TYPE: MLModelType = 'xgboost_3class';

/**
 * Fallback — prefer direction from backend config.
 */
export const DEFAULT_MODEL_DIRECTION: ModelDirection = 'both';

// =============================================================================
// Target Types (Sprint 2.0a + trading_bots integration)
// =============================================================================

/**
 * Available target labeling strategies.
 *
 * IMPORTANT: This is a FALLBACK only!
 * - Primary source: Backend GET /api/v1/config/public
 * - Frontend useAppConfig hook fetches from backend
 * - These values used ONLY if backend is unavailable
 *
 * WHY backend as single source of truth (per .cursorrules)?
 * - Add new targets without frontend redeploy
 * - Backend TargetFactory.list_registered() returns dynamically
 * - No config drift between frontend/backend
 *
 * @see apps/api/src/api/v1/endpoints/config.py
 * @see docs/02-technical/ML_PIPELINE.md
 */
export type TargetType =
  | 'threshold'
  | 'volatility'
  | 'returns'
  | 'atr_based'
  | 'technical_filtered'
  | 'binary'
  | 'weighted_scoring'
  | 'hft_scalping'
  | 'bottom_detection'
  | 'support_bounce'
  | 'simple_bottom'
  | 'regression'
  | 'adaptive_quantile'
  | 'regime_based'
  | 'trend_following'
  | 'trend_scanning'
  | 'mean_reversion';

/**
 * Target type options for Select components.
 * Fallback — prefer config.training.target_type_options from useAppConfig().
 *
 * Grouped by category:
 * 1. Standard: threshold-based targets
 * 2. Pattern: pattern detection targets
 * 3. Scoring: multi-factor scoring targets
 */
export const TARGET_TYPE_OPTIONS: SelectOption<TargetType>[] = [
  // 3-class targets (BUY/SELL/HOLD) — threshold variants
  { value: 'threshold', label: 'Fixed Threshold (±1%)' },
  { value: 'volatility', label: 'Volatility Scaled (2σ)' },
  { value: 'atr_based', label: 'ATR-Based (1.5x ATR)' },
  { value: 'returns', label: 'Max Returns (Best Exit)' },
  { value: 'technical_filtered', label: 'Technical Filtered (RSI)' },
  // 3-class targets — strategic gap fills
  { value: 'adaptive_quantile', label: 'Adaptive Quantile (Rolling Percentile)' },
  { value: 'regime_based', label: 'Regime-Based (Vol Regime Adaptive)' },
  { value: 'trend_following', label: 'Trend Following (EMA + ADX)' },
  { value: 'mean_reversion', label: 'Mean Reversion (Bollinger Z-Score)' },
  // 2-class targets (pattern detection)
  { value: 'bottom_detection', label: 'Bottom Detection (Multi-horizon)' },
  { value: 'support_bounce', label: 'Support Bounce (Volume Confirmed)' },
  { value: 'simple_bottom', label: 'Simple Bottom (Near Low + Recovery)' },
  // Scoring-based targets
  { value: 'weighted_scoring', label: 'Weighted Scoring (Multi-factor)' },
  { value: 'hft_scalping', label: 'HFT Scalping (5m, 0.15% moves)' },
  // Binary / regression targets (Sprint 2.9b)
  { value: 'binary', label: 'Binary (Up/Down)' },
  { value: 'regression', label: 'Regression (Continuous Returns)' },
];

/**
 * Fallback — prefer default from backend /config/public.
 */
export const DEFAULT_TARGET_TYPE: TargetType = 'volatility';

/**
 * Default max features to keep after feature selection.
 * Single source of truth for FE — mirrors BE's DEFAULT_MAX_FEATURES in feature_selection.py.
 * Used as initial form value before /config/public responds with default_max_features.
 */
export const DEFAULT_MAX_FEATURES = 25;

/**
 * Mirrors BE DEFAULT_MIN_FEATURES_AFTER_SELECTION — minimum final feature count when the pool allows.
 */
export const DEFAULT_MIN_FEATURES_AFTER_SELECTION = 3;

/**
 * Hard upper bound on a user-requested max_features (input cap + hint).
 * Mirrors BE MAX_FEATURES_LIMIT in shared/constants/features.py — change both together.
 * WHY 50: overfitting guard (events-per-variable); the model self-selects ~14, so this
 * never binds the selection — it only stops a manual request for an overfit count.
 */
export const MAX_FEATURES_LIMIT = 50;

/**
 * Default meta-gate probability threshold: P(profitable) below which the primary signal is
 * suppressed to HOLD. SoT for FE — mirrors BE DEFAULT_META_GATE_THRESHOLD in
 * shared/constants/training_defaults.py. Initial value for the meta-labeling threshold slider.
 */
export const DEFAULT_META_GATE_THRESHOLD = 0.5;

/** Meta-gate threshold is a probability — bounded [0, 1]; the slider steps in 0.01. */
export const META_GATE_THRESHOLD_MIN = 0;
export const META_GATE_THRESHOLD_MAX = 1;
export const META_GATE_THRESHOLD_STEP = 0.01;

/**
 * Bounds for the optional meta-label holding-periods override (bars held before a trade times
 * out). Mirrors BE TrainingConfigRequest.meta_holding_periods (`ge=1`). MAX is a generous UI guard
 * against an absurd manual entry, not a domain limit (BE imposes no upper bound).
 */
export const META_HOLDING_PERIODS_MIN = 1;
export const META_HOLDING_PERIODS_MAX = 500;
