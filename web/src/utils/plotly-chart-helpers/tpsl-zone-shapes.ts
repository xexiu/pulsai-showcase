/**
 * TP/SL zone rectangle shapes for Plotly backtest chart.
 *
 * Entry signals carry `stop_loss_price` / `take_profit_price` from the backtester.
 * Each entry is paired with the next EXIT signal to determine the zone's x-span.
 */

import { resolveEntryActiveWindow } from '@/utils/plotly-chart-helpers/entry-active-window';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

const TPSL_SL_FILL = 'rgba(255, 82, 82, 0.18)';
const TPSL_SL_LINE = 'rgba(255, 82, 82, 0.45)';
const TPSL_MIN_TP_FILL = 'rgba(144,238,144,0.20)';
const TPSL_MIN_TP_LINE = 'rgba(34,139,34,0.35)';
const TPSL_1R_FILL = 'rgba(168,255,172,0.20)';
const TPSL_1R_LINE = 'rgba(46,160,67,0.35)';
const TPSL_FULL_TP_FILL = 'rgba(0,100,0,0.15)';
const TPSL_FULL_TP_LINE = 'rgba(0,100,0,0.35)';

export type PlotlyShape = {
  type: 'rect' | 'line';
  xref: string;
  yref: string;
  x0: number | string;
  y0: number;
  x1: number | string;
  y1: number;
  fillcolor?: string;
  line?: { color: string; width: number; dash?: 'dot' };
  layer?: string;
};

type ZoneRectParams = {
  x0: number;
  x1: number;
  entryPrice: number;
  levelPrice: number;
  fill: string;
  lineColor: string;
};

function makeZoneRect(p: ZoneRectParams): PlotlyShape {
  return {
    type: 'rect',
    xref: 'x',
    yref: 'y',
    x0: p.x0,
    y0: Math.min(p.entryPrice, p.levelPrice),
    x1: p.x1,
    y1: Math.max(p.entryPrice, p.levelPrice),
    fillcolor: p.fill,
    line: { color: p.lineColor, width: 1 },
    layer: 'below',
  };
}

/**
 * Build Plotly layout.shapes for TP/SL zone rectangles.
 *
 * Green rect = TP zone (entry price → TP price), red rect = SL zone (entry price → SL price).
 */
export function createTpSlZoneShapes(
  signals: SignalData[],
  plotlyTime: PlotlyTimeOptions,
  fallbackEndTimestamp?: string
): PlotlyShape[] {
  const shapes: PlotlyShape[] = [];

  const entries = signals.filter(
    (s) =>
      (s.type === 'BUY' || s.type === 'SELL') &&
      (s.stop_loss_price != null ||
        s.take_profit_price != null ||
        s.stop_loss != null ||
        s.take_profit != null)
  );

  for (const entry of entries) {
    const { x0, x1 } = resolveEntryActiveWindow(entry, signals, plotlyTime, fallbackEndTimestamp);

    const takeProfitPrice = entry.take_profit_price ?? entry.take_profit;
    const stopLossPrice = entry.stop_loss_price ?? entry.stop_loss;
    const minTpPrice = entry.min_tp_price ?? takeProfitPrice;
    const oneRPrice = entry.tp_1r_price;
    const fullTpPrice = entry.full_tp_price;

    if (stopLossPrice != null) {
      shapes.push(
        makeZoneRect({
          x0,
          x1,
          entryPrice: entry.price,
          levelPrice: stopLossPrice,
          fill: TPSL_SL_FILL,
          lineColor: TPSL_SL_LINE,
        })
      );
    }

    if (minTpPrice != null) {
      shapes.push(
        makeZoneRect({
          x0,
          x1,
          entryPrice: entry.price,
          levelPrice: minTpPrice,
          fill: TPSL_MIN_TP_FILL,
          lineColor: TPSL_MIN_TP_LINE,
        })
      );
    }

    if (minTpPrice != null && oneRPrice != null && oneRPrice !== minTpPrice) {
      shapes.push(
        makeZoneRect({
          x0,
          x1,
          entryPrice: minTpPrice,
          levelPrice: oneRPrice,
          fill: TPSL_1R_FILL,
          lineColor: TPSL_1R_LINE,
        })
      );
    }

    if (minTpPrice != null && fullTpPrice != null && fullTpPrice !== minTpPrice) {
      shapes.push(
        makeZoneRect({
          x0,
          x1,
          entryPrice: minTpPrice,
          levelPrice: fullTpPrice,
          fill: TPSL_FULL_TP_FILL,
          lineColor: TPSL_FULL_TP_LINE,
        })
      );
    }
  }

  return shapes;
}
