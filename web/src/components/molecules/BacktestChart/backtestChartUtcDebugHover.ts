/**
 * Pure hover text for `BacktestChartUtcDebug`: only BE candle fields, no
 * `createCandlestickData` / unified-multi-trace path — isolates Plotly display issues.
 */

import type { SignalChartCandle } from '@/types/signal-chart';
import { formatPrice } from '@/utils/formatters';

/**
 * Build HTML hover lines for the UTC debug candlestick trace.
 *
 * @param chartMlModelHover - when false, omits ML lines (matches backtest ML hover flag).
 */
export function buildBacktestUtcDebugHoverText(
  c: SignalChartCandle,
  chartMlModelHover: boolean
): string {
  const lines = [
    '<b>UTC debug (BE only)</b>',
    `BE timestamp: ${c.timestamp}`,
    `Open: ${formatPrice(c.open)}`,
    `High: ${formatPrice(c.high)}`,
    `Low: ${formatPrice(c.low)}`,
    `Close: ${formatPrice(c.close)}`,
    '<i>Single candlestick trace — no signal markers (avoids unified hover stacking).</i>',
  ];

  if (chartMlModelHover) {
    lines.push(`BE ml_prediction: ${c.ml_prediction == null ? 'null' : String(c.ml_prediction)}`);
    lines.push(
      `BE ml_confidence_percent: ${c.ml_confidence_percent == null ? 'null' : String(c.ml_confidence_percent)}`
    );
  }

  return lines.join('<br>');
}
