/**
 * Vertical position for backtest entry scatter markers (BUY/SELL) vs OHLC candle.
 */

import {
  ENTRY_SIGNAL_MARKER_PAD_FRACTION_OF_RANGE,
  ENTRY_SIGNAL_MARKER_PAD_MIN_FRACTION_OF_CLOSE,
} from '@/utils/plotly-chart-helpers/constants';
import type { CandleData } from '@/utils/plotly-chart-helpers/types';

/**
 * BUY: slightly below candle low (triangle-up reads as “under” the bar).
 * SELL: slightly above candle high (triangle-down reads as “over” the bar).
 */
export function yForEntrySignalMarker(candle: CandleData, isBuy: boolean): number {
  const range = Math.max(candle.high - candle.low, 0);
  const padFromRange = range * ENTRY_SIGNAL_MARKER_PAD_FRACTION_OF_RANGE;
  const padMin = Math.abs(candle.close) * ENTRY_SIGNAL_MARKER_PAD_MIN_FRACTION_OF_CLOSE;
  const pad = Math.max(padFromRange, padMin);

  if (isBuy) {
    return candle.low - pad;
  }

  return candle.high + pad;
}
