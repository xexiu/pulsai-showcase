/**
 * Backtest overlay: liquidation heatmap bands at entry time (Phase 4 B.2).
 *
 * Horizontal bands span each trade's active window (entry → exit).
 */

import type {
  LiquidationHeatmapBandSide,
  LiquidationHeatmapResponse,
} from '@/types/chart-liquidation-heatmap';
import { selectLiquidationHeatmapBandsForDraw } from '@/utils/chart-liquidation-heatmap-bands';
import {
  resolveLiquidationHeatmapBandAlpha,
  resolveLiquidationHeatmapBandThicknessPx,
} from '@/utils/chart-liquidation-heatmap-draw-metrics';
import { BACKTEST_LIQUIDATION_HEATMAP_DRAW_PREFERENCES } from '@/utils/constants/backtestLiquidationHeatmap';
import { LIQUIDATION_HEATMAP_SIDE_RGB_CHANNELS } from '@/utils/constants/chartLiquidationHeatmap';
import { resolveEntryActiveWindow } from '@/utils/plotly-chart-helpers/entry-active-window';
import type { PlotlyShape } from '@/utils/plotly-chart-helpers/tpsl-zone-shapes';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

const PLOTLY_LINE_WIDTH_MAX = 4;
const PLOTLY_THICKNESS_BASE_PX = 2;

function resolveSideRgba(side: LiquidationHeatmapBandSide, alpha: number): string {
  return `rgba(${LIQUIDATION_HEATMAP_SIDE_RGB_CHANNELS[side]}, ${alpha})`;
}

function resolvePlotlyLineWidth(normalizedIntensity: number): number {
  const thicknessPx = resolveLiquidationHeatmapBandThicknessPx(
    PLOTLY_THICKNESS_BASE_PX,
    normalizedIntensity
  );

  return Math.max(1, Math.min(PLOTLY_LINE_WIDTH_MAX, thicknessPx));
}

function makeBandShape(
  x0: number,
  x1: number,
  price: number,
  color: string,
  width: number
): PlotlyShape {
  return {
    type: 'line',
    xref: 'x',
    yref: 'y',
    x0,
    x1,
    y0: price,
    y1: price,
    line: { color, width },
    layer: 'below',
  };
}

/**
 * Build Plotly layout.shapes for historical liquidation heatmap bands per entry window.
 */
export function createBacktestLiquidationHeatmapShapes(
  signals: SignalData[],
  enabled: boolean,
  snapshotsByEntryKey: ReadonlyMap<string, LiquidationHeatmapResponse>,
  plotlyTime: PlotlyTimeOptions,
  fallbackEndTimestamp?: string
): PlotlyShape[] {
  if (!enabled || snapshotsByEntryKey.size === 0) {
    return [];
  }

  const shapes: PlotlyShape[] = [];
  const entries = signals.filter((signal) => signal.type === 'BUY' || signal.type === 'SELL');

  for (const entry of entries) {
    const snapshot = snapshotsByEntryKey.get(entry.timestamp);

    if (snapshot == null || snapshot.bands.length === 0) {
      continue;
    }

    const bands = selectLiquidationHeatmapBandsForDraw(
      snapshot,
      BACKTEST_LIQUIDATION_HEATMAP_DRAW_PREFERENCES
    );

    if (bands.length === 0) {
      continue;
    }

    const { x0, x1 } = resolveEntryActiveWindow(entry, signals, plotlyTime, fallbackEndTimestamp);

    for (const band of bands) {
      const alpha = resolveLiquidationHeatmapBandAlpha(band.normalizedIntensity);
      const color = resolveSideRgba(band.side, alpha);
      const width = resolvePlotlyLineWidth(band.normalizedIntensity);

      shapes.push(makeBandShape(x0, x1, band.price, color, width));
    }
  }

  return shapes;
}
