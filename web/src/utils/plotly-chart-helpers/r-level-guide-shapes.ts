import { resolveEntryActiveWindow } from '@/utils/plotly-chart-helpers/entry-active-window';
import type { PlotlyShape } from '@/utils/plotly-chart-helpers/tpsl-zone-shapes';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

const R_GUIDE_ONE_R_COLOR = 'rgba(59, 130, 246, 0.8)';
const R_GUIDE_MIN_TP_COLOR = 'rgba(234, 179, 8, 0.8)';
const R_GUIDE_LINE_WIDTH = 1;
const R_GUIDE_DASH = 'dot';
const R_GUIDE_EPSILON = 1e-9;

type EntrySignal = SignalData & {
  type: 'BUY' | 'SELL';
  stop_loss_price?: number;
  stop_loss?: number;
  take_profit_price?: number;
  take_profit?: number;
};

function isEntryWithTpSl(signal: SignalData): signal is EntrySignal {
  return (
    (signal.type === 'BUY' || signal.type === 'SELL') &&
    (typeof signal.stop_loss_price === 'number' || typeof signal.stop_loss === 'number') &&
    (typeof signal.take_profit_price === 'number' || typeof signal.take_profit === 'number')
  );
}

function computeOneRPrice(entry: EntrySignal): number {
  const isLong = entry.type === 'BUY';
  const stopLossPrice = entry.stop_loss_price ?? entry.stop_loss;

  if (stopLossPrice == null) {
    return entry.price;
  }
  const riskDistance = Math.abs(entry.price - stopLossPrice);

  return isLong ? entry.price + riskDistance : entry.price - riskDistance;
}

function makeGuideLine({
  x0,
  x1,
  price,
  color,
}: {
  x0: number;
  x1: number;
  price: number;
  color: string;
}): PlotlyShape {
  return {
    type: 'line',
    xref: 'x',
    yref: 'y',
    x0,
    x1,
    y0: price,
    y1: price,
    line: { color, width: R_GUIDE_LINE_WIDTH, dash: R_GUIDE_DASH },
    layer: 'above',
  };
}

export function createRLevelGuideShapes(
  signals: SignalData[],
  enabled: boolean,
  plotlyTime: PlotlyTimeOptions,
  fallbackEndTimestamp?: string
): PlotlyShape[] {
  if (!enabled) {
    return [];
  }

  const shapes: PlotlyShape[] = [];
  const entries = signals.filter(isEntryWithTpSl);

  for (const entry of entries) {
    const { x0, x1 } = resolveEntryActiveWindow(entry, signals, plotlyTime, fallbackEndTimestamp);
    const oneRPrice = computeOneRPrice(entry);
    const minTpPrice = entry.take_profit_price ?? entry.take_profit;

    if (minTpPrice == null) {
      continue;
    }

    shapes.push(makeGuideLine({ x0, x1, price: oneRPrice, color: R_GUIDE_ONE_R_COLOR }));
    if (Math.abs(minTpPrice - oneRPrice) > R_GUIDE_EPSILON) {
      shapes.push(makeGuideLine({ x0, x1, price: minTpPrice, color: R_GUIDE_MIN_TP_COLOR }));
    }
  }

  return shapes;
}
