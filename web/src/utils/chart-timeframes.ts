/**
 * Chart timeframe resolution utilities.
 *
 * Single source: @pulsai/shared ENABLED_TIMEFRAMES (matches BE supported_timeframes).
 * Used when a component accepts optional timeframes and must fall back to the default list.
 */

import { ENABLED_TIMEFRAMES } from '@pulsai/shared';

import type { Timeframe } from '@/types/chart';

/**
 * Resolves timeframes for chart selectors: use prop when non-empty, else shared fallback.
 *
 * WHY EXTRACTED?
 * - Testable (no inline helper in components).
 * - DRY: same logic in TechnicalAnalysisSection and FullChartPageContent.
 * - Single fallback source: ENABLED_TIMEFRAMES from shared.
 *
 * @param prop - Optional timeframes from parent (e.g. from useTradingConfig).
 * @returns prop if length > 0, else ENABLED_TIMEFRAMES.
 */
export function getResolvedChartTimeframes(prop: Timeframe[] | null | undefined): Timeframe[] {
  if (prop != null && prop.length > 0) {
    return prop;
  }

  return ENABLED_TIMEFRAMES as Timeframe[];
}
