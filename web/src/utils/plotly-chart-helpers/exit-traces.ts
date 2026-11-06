import {
  buildSignalExitHoverText,
  type ChartHoverLabels,
} from '@/utils/plotly-chart-helpers/chart-hover-labels';
import type {
  EquityData,
  PlotlyData,
  SignalData,
  ThemeColors,
} from '@/utils/plotly-chart-helpers/types';
import { mapTimestampForPlotlyTrace, type PlotlyTimeOptions } from '@/utils/plotly-chart-time';

function getExitMarkerColor(signal: SignalData, colors: ThemeColors): string {
  if (signal.net_pnl !== undefined) {
    if (signal.net_pnl > 0) return colors.bullish;
    if (signal.net_pnl < 0) return colors.bearish;

    return colors.textMuted;
  }
  if (signal.side === 'short') return colors.bullish;

  return colors.bearish;
}

export function createExitData(
  signals: SignalData[],
  colors: ThemeColors,
  plotlyTime: PlotlyTimeOptions,
  hoverLabels?: ChartHoverLabels
): PlotlyData | null {
  const exits = signals.filter((s) => s.type === 'EXIT');

  if (exits.length === 0) {
    return null;
  }

  const hoverTexts = exits.map((s) => buildSignalExitHoverText(s, hoverLabels));

  return {
    type: 'scatter',
    mode: 'markers',
    name: 'EXIT',
    xaxis: 'x',
    yaxis: 'y',
    x: exits.map((s) => mapTimestampForPlotlyTrace(s.timestamp, plotlyTime)),
    y: exits.map((s) => s.price),
    marker: {
      symbol: 'x',
      size: 8,
      color: exits.map((s) => getExitMarkerColor(s, colors)),
      opacity: 0.7,
      line: { color: colors.paper, width: 1 },
    },
    text: hoverTexts,
    hovertemplate: '%{text}<extra></extra>',
  };
}

export function createEquityData(
  equity: EquityData[] | undefined,
  show: boolean,
  colors: ThemeColors,
  plotlyTime: PlotlyTimeOptions
): PlotlyData | null {
  if (!show || !equity || equity.length === 0) {
    return null;
  }

  return {
    type: 'scatter',
    mode: 'lines',
    name: 'Equity',
    yaxis: 'y2',
    x: equity.map((e) => mapTimestampForPlotlyTrace(e.timestamp, plotlyTime)),
    y: equity.map((e) => e.value),
    line: { color: colors.signal, width: 2 },
    hovertemplate: 'Equity: $%{y:,.2f}<extra></extra>',
  };
}
