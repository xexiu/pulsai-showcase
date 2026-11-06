/**
 * Plotly x-axis: **real UTC epoch ms** only.
 *
 * WHY not `timeToTz` / `mapUtcBarOpenSecondsForChartDisplay` (LWC path)?
 * - Those produce “fake UTC” seconds for lightweight-charts + a matching UTC `timeFormatter`.
 * - Plotly’s `type: 'date'` interprets ms as **real** instants; `timeToTz` + `xaxis.utc` double-applies
 *   the zone offset (e.g. +2h in Europe/Madrid vs UTC).
 *
 * WHY not signal `candle_open_local_iso`?
 * - Per-signal display fields, not a full OHLCV series for backtest candles.
 *
 * Axis labels: `layout.xaxis.utc: true` → ticks in UTC (same as API / exchange bar open).
 */

import { timestampToChartTime } from '@/utils/chart-timestamp';

export type PlotlyTimeOptions = {
  /** Reserved for future tick/hover customization; x values are always UTC ms. */
  chartTimezone: string;
  timeframe: string;
};

/**
 * Convert backend candle/event timestamp to Plotly `x` milliseconds (UTC epoch).
 */
export function timestampToPlotlyXMs(
  timestamp: string | number,
  _chartTimezone: string,
  _timeframe: string | undefined
): number {
  const sec = timestampToChartTime(timestamp);

  if (!Number.isFinite(sec) || sec <= 0) {
    return Number.NaN;
  }

  return sec * 1000;
}

/**
 * Map a trace timestamp; falls back to `Date.parse` only when normalization fails (should be rare).
 */
export function mapTimestampForPlotlyTrace(
  timestamp: string | number,
  plotlyTime: PlotlyTimeOptions
): number {
  const ms = timestampToPlotlyXMs(timestamp, plotlyTime.chartTimezone, plotlyTime.timeframe);

  if (Number.isFinite(ms)) {
    return ms;
  }

  const parsed = Date.parse(String(timestamp));

  return Number.isFinite(parsed) ? parsed : Number.NaN;
}
