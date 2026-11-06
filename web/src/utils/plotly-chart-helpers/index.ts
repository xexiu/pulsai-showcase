/**
 * Plotly Chart Helpers (Sprint 2.3)
 *
 * WHY EXTRACTED?
 * - Testability: Each function can be unit tested independently
 * - Reusability: Other chart components can use same helpers
 * - SRP: Hook orchestrates, helpers do the work
 *
 * @see docs/04-structural/CODING_STANDARDS.md
 */

export {
  RSI_OVERBOUGHT,
  RSI_OVERSOLD,
  SUBPLOT_GAP,
  SUBPLOT_HEIGHT,
} from '@/utils/plotly-chart-helpers/constants';
export { getThemeColors } from '@/utils/plotly-chart-helpers/theme';
export {
  createCandlestickData,
  createCompoundFillData,
  createDynamicRegimeHintData,
  createEquityData,
  createExitData,
  createSignalData,
} from '@/utils/plotly-chart-helpers/traces';
export { createPredictionData } from '@/utils/plotly-chart-helpers/prediction-traces';
export { createLiquidationGuideShapes } from '@/utils/plotly-chart-helpers/liquidation-guide-shapes';
export { createBacktestLiquidationHeatmapShapes } from '@/utils/plotly-chart-helpers/backtest-liquidation-heatmap-shapes';
export { createRLevelGuideShapes } from '@/utils/plotly-chart-helpers/r-level-guide-shapes';
export { createTpSlZoneShapes } from '@/utils/plotly-chart-helpers/tpsl-zone-shapes';
export type { PlotlyShape } from '@/utils/plotly-chart-helpers/tpsl-zone-shapes';
export type {
  BBData,
  CandleData,
  EquityData,
  LayoutOptions,
  MACDData,
  PlotlyData,
  RSIData,
  SignalData,
  ThemeColors,
} from '@/utils/plotly-chart-helpers/types';
export {
  DYNAMIC_VOLATILITY_REGIME_ORDER,
  getDynamicVolatilityRegimeDotClass,
  toDynamicVolatilityRegime,
} from '@/utils/plotly-chart-helpers/dynamic-regime';
