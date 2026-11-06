/**
 * Candlestick trace hover HTML (Price panel): bar open/close times + OHLC (+ ML when enabled).
 *
 * Aligns with trading_bots PRICE_INFO: open_date, close_date (derived as open + period when TF known),
 * then open/high/low/close prices.
 *
 * Model feature vectors are intentionally omitted from hover — they clutter the unified
 * Plotly tooltip on backtest charts. Prediction / confidence stay when `chartMlModelHover`.
 */

import { getTimeframeSeconds } from '@/utils/chart-time';
import { timestampToChartTime } from '@/utils/chart-timestamp';
import { formatPrice } from '@/utils/formatters';
import { formatChartTooltipTime } from '@/utils/formatters/datetime';
import type { CandleData } from '@/utils/plotly-chart-helpers/types';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

function barOpenHoverLine(iso: string, chartTimezone: string): string | null {
  const sec = timestampToChartTime(iso);

  if (!Number.isFinite(sec) || sec <= 0) {
    return null;
  }

  return `Bar open: ${formatChartTooltipTime(sec, chartTimezone)}`;
}

/** Bar close instant = open + period (same SoT as signal tooltip matching). */
function barCloseHoverLine(iso: string, chartTimezone: string, timeframe: string): string | null {
  const openSec = timestampToChartTime(iso);
  const periodSec = getTimeframeSeconds(timeframe);

  if (!Number.isFinite(openSec) || openSec <= 0 || periodSec <= 0) {
    return null;
  }

  const closeSec = openSec + periodSec;

  return `Bar close: ${formatChartTooltipTime(closeSec, chartTimezone)}`;
}

export function buildCandlestickHoverText(
  c: CandleData,
  chartMlModelHover: boolean | undefined,
  plotlyTime: PlotlyTimeOptions
): string {
  const timeLines: string[] = [];
  const openLine = barOpenHoverLine(c.timestamp, plotlyTime.chartTimezone);
  const closeLine = barCloseHoverLine(c.timestamp, plotlyTime.chartTimezone, plotlyTime.timeframe);

  if (openLine) {
    timeLines.push(openLine);
  }

  if (closeLine) {
    timeLines.push(closeLine);
  }

  const lines = [
    ...timeLines,
    `Open: ${formatPrice(c.open)}`,
    `High: ${formatPrice(c.high)}`,
    `Low: ${formatPrice(c.low)}`,
    `Close: ${formatPrice(c.close)}`,
  ];

  if (chartMlModelHover) {
    const pred = c.ml_prediction;
    const confPct = c.ml_confidence_percent;

    if (pred === 'BUY' || pred === 'SELL' || pred === 'HOLD') {
      if (confPct != null && Number.isFinite(confPct)) {
        lines.push(`${pred} · ${confPct.toFixed(1)}%`);
      } else {
        lines.push(pred);
      }
    }
  }

  return lines.join('<br>');
}
