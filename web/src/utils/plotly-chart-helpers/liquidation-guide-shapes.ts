/**
 * Perp liquidation overlay: theoretical liq line + slippage gap to actual fill (EXIT marker).
 */

import { BACKTEST_EXIT_TYPE } from '@/utils/constants/backtestExitTypes';
import { resolveEntryActiveWindow } from '@/utils/plotly-chart-helpers/entry-active-window';
import type { PlotlyShape } from '@/utils/plotly-chart-helpers/tpsl-zone-shapes';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';
import { mapTimestampForPlotlyTrace } from '@/utils/plotly-chart-time';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

const LIQ_THEORETICAL_LINE_COLOR = 'rgba(249, 115, 22, 0.85)';
const LIQ_SLIPPAGE_GAP_COLOR = 'rgba(239, 68, 68, 0.75)';
const LIQ_GUIDE_LINE_WIDTH = 1.5;
const LIQ_GUIDE_DASH = 'dot';

type LiquidationExitSignal = SignalData & {
  type: 'EXIT';
  theoretical_liquidation_price: number;
};

function isLiquidationExit(signal: SignalData): signal is LiquidationExitSignal {
  return (
    signal.type === 'EXIT' &&
    signal.reason === BACKTEST_EXIT_TYPE.LIQUIDATION &&
    typeof signal.theoretical_liquidation_price === 'number' &&
    Number.isFinite(signal.theoretical_liquidation_price)
  );
}

function makeHorizontalGuide(x0: number, x1: number, price: number, color: string): PlotlyShape {
  return {
    type: 'line',
    xref: 'x',
    yref: 'y',
    x0,
    x1,
    y0: price,
    y1: price,
    line: { color, width: LIQ_GUIDE_LINE_WIDTH, dash: LIQ_GUIDE_DASH },
    layer: 'above',
  };
}

function makeSlippageGapLine(x: number, theoretical: number, fill: number): PlotlyShape {
  return {
    type: 'line',
    xref: 'x',
    yref: 'y',
    x0: x,
    x1: x,
    y0: theoretical,
    y1: fill,
    line: { color: LIQ_SLIPPAGE_GAP_COLOR, width: LIQ_GUIDE_LINE_WIDTH },
    layer: 'above',
  };
}

/**
 * Build Plotly layout.shapes for liquidation trades (theoretical liq vs fill).
 */
export function createLiquidationGuideShapes(
  signals: SignalData[],
  enabled: boolean,
  plotlyTime: PlotlyTimeOptions,
  fallbackEndTimestamp?: string
): PlotlyShape[] {
  if (!enabled) {
    return [];
  }

  const shapes: PlotlyShape[] = [];
  const liquidationExits = signals.filter(isLiquidationExit);

  for (const exit of liquidationExits) {
    const entry = signals
      .filter(
        (signal) =>
          (signal.type === 'BUY' || signal.type === 'SELL') &&
          signal.timestamp < exit.timestamp &&
          (exit.side == null || signal.side === exit.side)
      )
      .at(-1);

    if (entry == null) {
      continue;
    }

    const { x0, x1 } = resolveEntryActiveWindow(entry, signals, plotlyTime, fallbackEndTimestamp);
    const theoretical = exit.theoretical_liquidation_price;

    shapes.push(
      makeHorizontalGuide(x0, x1, theoretical, LIQ_THEORETICAL_LINE_COLOR),
      makeSlippageGapLine(
        mapTimestampForPlotlyTrace(exit.timestamp, plotlyTime),
        theoretical,
        exit.price
      )
    );
  }

  return shapes;
}
