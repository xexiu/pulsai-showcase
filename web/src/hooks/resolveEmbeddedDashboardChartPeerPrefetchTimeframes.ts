import type { Timeframe } from '@/types/chart';

/**
 * Peer TF warm list for embedded charts. Dashboard excludes tier-disabled TFs; trade uses all allowed.
 */
export function resolveEmbeddedDashboardChartPeerPrefetchTimeframes(
  allowedTimeframes: readonly Timeframe[],
  disabledTimeframes?: readonly Timeframe[]
): Timeframe[] {
  if (disabledTimeframes == null || disabledTimeframes.length === 0) {
    return [...allowedTimeframes];
  }

  const disabled = new Set(disabledTimeframes);

  return allowedTimeframes.filter((timeframe) => !disabled.has(timeframe));
}
