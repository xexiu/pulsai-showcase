/**
 * Plotly Chart Layout & Config (extracted for max-lines compliance)
 *
 * WHY SEPARATE FILE:
 * - plotly-chart-helpers.ts exceeded 400-line limit
 * - SRP: Layout/config is distinct from data creators
 * - Re-exports from main helpers for backward compatibility
 *
 * @see docs/04-structural/CODING_STANDARDS.md Section 7.2
 */

import type { PlotlyConfig, PlotlyLayout } from '@/types/plotly-layout';
import type { LayoutOptions } from '@/utils/plotly-chart-helpers';
import { SUBPLOT_GAP, SUBPLOT_HEIGHT } from '@/utils/plotly-chart-helpers';
import type { PlotlyShape } from '@/utils/plotly-chart-helpers/tpsl-zone-shapes';

// =============================================================================
// Layout
// =============================================================================

/**
 * X-axis title for backtest Plotly: UTC instants on x; optional LWC IANA for user context.
 *
 * WHY not change Plotly tick TZ here: `plotly-chart-time.ts` — avoid LWC `timeToTz` on Plotly ms.
 */
export function formatBacktestPlotlyXAxisTitle(chartDisplayTimezone?: string | null): string {
  const raw = chartDisplayTimezone?.trim() ?? '';

  if (raw === '' || raw.toUpperCase() === 'UTC') {
    return 'Time (UTC)';
  }

  return `Time (UTC) · LWC chart: ${raw}`;
}

/**
 * Create Plotly layout configuration for backtest chart.
 *
 * WHY complex domain calculation?
 * - Multiple subplots (price, RSI, MACD) need vertical space allocation
 * - Dynamic based on which indicators are enabled
 */
export function createChartLayout(opts: LayoutOptions): PlotlyLayout {
  const {
    symbol,
    timeframe,
    showEquityCurve,
    hasRSI,
    hasMACD,
    colors,
    chartDisplayTimezone,
    chartHeight,
  } = opts;

  let yPosition = 0;
  const macdDomain = hasMACD ? [yPosition, yPosition + SUBPLOT_HEIGHT] : undefined;

  if (hasMACD) yPosition += SUBPLOT_GAP;

  const rsiDomain = hasRSI ? [yPosition, yPosition + SUBPLOT_HEIGHT] : undefined;

  if (hasRSI) yPosition += SUBPLOT_GAP;

  const priceDomain = [yPosition, 1];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layout: Record<string, any> = {
    title: {
      text: `${symbol} ${timeframe} - Backtest Results`,
      font: { size: 16, color: colors.text },
    },
    xaxis: {
      rangeslider: { visible: false },
      type: 'date',
      // Real UTC epoch ms on traces; do not use LWC timeToTz fake-UTC here (Plotly interprets ms as real instants).
      utc: true,
      title: {
        text: formatBacktestPlotlyXAxisTitle(chartDisplayTimezone),
        font: { size: 11, color: colors.textMuted },
      },
      gridcolor: colors.grid,
      linecolor: colors.line,
      tickfont: { color: colors.textMuted },
    },
    yaxis: {
      title: 'Price',
      side: 'right',
      domain: priceDomain,
      gridcolor: colors.grid,
      linecolor: colors.line,
      tickfont: { color: colors.textMuted },
      titlefont: { color: colors.textMuted },
    },
    legend: {
      orientation: 'h',
      y: 1.02,
      x: 0.5,
      xanchor: 'center',
      font: { color: colors.textMuted, size: 10 },
    },
    margin: { t: 60, b: 40, l: 60, r: 60 },
    hovermode: 'x unified',
    paper_bgcolor: colors.paper,
    plot_bgcolor: colors.plot,
    ...(chartHeight !== undefined ? { height: chartHeight } : {}),
  };

  if (showEquityCurve) {
    layout['yaxis2'] = {
      title: 'Equity ($)',
      side: 'right',
      overlaying: 'y',
      showgrid: false,
      tickfont: { color: colors.signal },
      titlefont: { color: colors.signal },
    };
  }

  if (hasRSI && rsiDomain) {
    layout['yaxis3'] = {
      title: 'RSI',
      side: 'left',
      domain: rsiDomain,
      range: [0, 100],
      gridcolor: colors.grid,
      linecolor: colors.line,
      tickfont: { color: colors.textMuted, size: 9 },
      titlefont: { color: colors.textMuted, size: 10 },
    };
  }

  if (hasMACD && macdDomain) {
    layout['yaxis4'] = {
      title: 'MACD',
      side: 'left',
      domain: macdDomain,
      gridcolor: colors.grid,
      linecolor: colors.line,
      tickfont: { color: colors.textMuted, size: 9 },
      titlefont: { color: colors.textMuted, size: 10 },
    };
  }

  return layout;
}

/**
 * Create Plotly config for chart interactions (export, toolbar).
 * Named createPlotlyChartConfig to avoid clash with createChartConfig in chart-config.ts (lightweight-charts).
 * @see docs/04-structural/FE_DUPLICATION_AUDIT.md §3
 */
export function createPlotlyChartConfig(symbol: string, timeframe: string): PlotlyConfig {
  return {
    displayModeBar: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    displaylogo: false,
    responsive: true,
    toImageButtonOptions: {
      format: 'png',
      filename: `backtest_${symbol.replace('/', '_')}_${timeframe}`,
      height: 800,
      width: 1200,
      scale: 2,
    },
  };
}

/**
 * Narrow Plotly `layout.shapes` from react-plotly's loosely typed layout record.
 * Avoids scattering `as unknown[]` at merge sites (BacktestChart overlays).
 */
export function parsePlotlyLayoutShapes(value: unknown): PlotlyShape[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(isPlotlyShapeLike);
}

function isPlotlyShapeLike(item: unknown): item is PlotlyShape {
  if (item === null || typeof item !== 'object') {
    return false;
  }
  const o = item as Record<string, unknown>;
  const kind = o['type'];

  if (kind !== 'rect' && kind !== 'line') {
    return false;
  }

  return typeof o['xref'] === 'string' && typeof o['yref'] === 'string';
}
