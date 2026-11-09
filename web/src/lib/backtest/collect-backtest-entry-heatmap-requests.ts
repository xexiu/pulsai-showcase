/**
 * Collect unique backtest entry timestamps for historical heatmap fetches.
 *
 * Dedupe is keyed on the raw `timestamp` string (not parsed `asOfMs`) on purpose: the
 * consumer (`createBacktestLiquidationHeatmapShapes`) resolves snapshots by exact
 * `signal.timestamp`, so the dedupe key must match that lookup key. The result is capped at
 * {@link BACKTEST_LIQUIDATION_HEATMAP_MAX_ENTRY_REQUESTS} to avoid a first-render request storm.
 *
 * When a candle window is provided, in-window entries are preferred so history charts that
 * only show a tail of OHLCV still get heatmap bands for the visible trades first.
 */

import { BACKTEST_LIQUIDATION_HEATMAP_MAX_ENTRY_REQUESTS } from '@/utils/constants/backtestLiquidationHeatmap';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';

export type BacktestEntryHeatmapRequest = {
  entryKey: string;
  asOfMs: number;
};

export type CollectBacktestEntryHeatmapRequestsOptions = {
  /** Inclusive candle-window start (ms). Prefer entries inside [start, end]. */
  windowStartMs?: number;
  /** Inclusive candle-window end (ms). */
  windowEndMs?: number;
  /** Override request cap (tests). Defaults to BACKTEST_LIQUIDATION_HEATMAP_MAX_ENTRY_REQUESTS. */
  maxRequests?: number;
};

function isInsideWindow(
  asOfMs: number,
  windowStartMs: number | undefined,
  windowEndMs: number | undefined
): boolean {
  if (windowStartMs == null || windowEndMs == null) {
    return true;
  }

  return asOfMs >= windowStartMs && asOfMs <= windowEndMs;
}

export function collectBacktestEntryHeatmapRequests(
  signals: SignalData[],
  options: CollectBacktestEntryHeatmapRequestsOptions = {}
): BacktestEntryHeatmapRequest[] {
  const maxRequests = options.maxRequests ?? BACKTEST_LIQUIDATION_HEATMAP_MAX_ENTRY_REQUESTS;
  const seen = new Set<string>();
  const inWindow: BacktestEntryHeatmapRequest[] = [];
  const outOfWindow: BacktestEntryHeatmapRequest[] = [];

  for (const signal of signals) {
    if (signal.type !== 'BUY' && signal.type !== 'SELL') {
      continue;
    }

    if (seen.has(signal.timestamp)) {
      continue;
    }

    const asOfMs = Date.parse(signal.timestamp);

    if (!Number.isFinite(asOfMs)) {
      continue;
    }

    seen.add(signal.timestamp);
    const request: BacktestEntryHeatmapRequest = { entryKey: signal.timestamp, asOfMs };

    if (isInsideWindow(asOfMs, options.windowStartMs, options.windowEndMs)) {
      inWindow.push(request);
    } else {
      outOfWindow.push(request);
    }
  }

  return [...inWindow, ...outOfWindow].slice(0, maxRequests);
}
