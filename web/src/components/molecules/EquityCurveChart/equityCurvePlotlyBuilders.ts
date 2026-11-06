/**
 * Pure Plotly trace/layout builders for equity charts (testable, no React).
 */

import type {
  EquityOverlaySeriesItem,
  EquityPointComparison,
} from '@/components/molecules/EquityCurveChart/types';
import type { PlotlyLayout, PlotlyTraceData } from '@/types/plotly-layout';
import type { SignalChartEquityPoint } from '@/types/signal-chart';
import type { ThemeColors } from '@/utils/plotly-chart-helpers';

export const PLOTLY_MODE_BAR_REMOVE = ['lasso2d', 'select2d'] as ['lasso2d', 'select2d'];

export function buildSingleModeTrace(
  equity: SignalChartEquityPoint[],
  lineColor: string,
  showFill: boolean,
  isDark: boolean
): PlotlyTraceData {
  const base = {
    type: 'scatter',
    mode: 'lines',
    x: equity.map((e) => e.timestamp),
    y: equity.map((e) => e.value),
    line: { color: lineColor, width: 2 },
    name: 'Equity',
    hovertemplate: '$%{y:,.2f}<extra></extra>',
  };

  if (showFill) {
    return {
      ...base,
      fill: 'tozeroy',
      fillcolor: isDark ? 'rgba(168, 85, 247, 0.1)' : 'rgba(168, 85, 247, 0.15)',
    };
  }

  return {
    ...base,
    fill: 'none',
  };
}

export function buildSingleModeLayout(
  colors: ThemeColors,
  params: {
    titleText: string;
    yAxisLabel: string;
  }
): PlotlyLayout {
  return {
    title: { text: params.titleText, font: { size: 14, color: colors.text } },
    xaxis: {
      type: 'date',
      gridcolor: colors.grid,
      tickfont: { color: colors.textMuted },
    },
    yaxis: {
      title: { text: params.yAxisLabel, font: { color: colors.textMuted } },
      side: 'right',
      gridcolor: colors.grid,
      tickfont: { color: colors.textMuted },
      tickformat: '$,.0f',
    },
    paper_bgcolor: colors.paper,
    plot_bgcolor: colors.plot,
    margin: { l: 50, r: 80, t: 40, b: 40 },
    showlegend: false,
    hovermode: 'x unified',
  };
}

export function buildComparisonTraces(
  equityCurves: EquityPointComparison[],
  strategyAName: string,
  strategyBName: string,
  strategyAColor: string,
  strategyBColor: string
): PlotlyTraceData[] {
  return [
    {
      type: 'scatter',
      mode: 'lines',
      x: equityCurves.map((e) => e.timestamp),
      y: equityCurves.map((e) => e.equity_a),
      line: { color: strategyAColor, width: 2 },
      name: strategyAName,
      hovertemplate: `${strategyAName}: $%{y:,.2f}<extra></extra>`,
    },
    {
      type: 'scatter',
      mode: 'lines',
      x: equityCurves.map((e) => e.timestamp),
      y: equityCurves.map((e) => e.equity_b),
      line: { color: strategyBColor, width: 2 },
      name: strategyBName,
      hovertemplate: `${strategyBName}: $%{y:,.2f}<extra></extra>`,
    },
  ];
}

export function buildComparisonLayout(
  colors: ThemeColors,
  params: { chartTitle: string; yAxisLabel: string }
): PlotlyLayout {
  return {
    title: {
      text: params.chartTitle,
      font: { size: 16, color: colors.text },
    },
    xaxis: {
      type: 'date',
      gridcolor: colors.grid,
      tickfont: { color: colors.textMuted },
    },
    yaxis: {
      title: { text: params.yAxisLabel },
      side: 'right',
      gridcolor: colors.grid,
      tickfont: { color: colors.textMuted },
      titlefont: { color: colors.textMuted },
    },
    legend: {
      orientation: 'h',
      y: 1.1,
      x: 0.5,
      xanchor: 'center',
      font: { color: colors.textMuted },
    },
    margin: { t: 60, b: 40, l: 40, r: 60 },
    hovermode: 'x unified',
    paper_bgcolor: colors.paper,
    plot_bgcolor: colors.plot,
  };
}

export function buildOverlayTraces(series: EquityOverlaySeriesItem[]): PlotlyTraceData[] {
  return series.map((s) => ({
    type: 'scatter',
    mode: 'lines',
    x: s.points.map((p) => p.timestamp),
    y: s.points.map((p) => p.value),
    line: {
      color: s.color,
      width: 2,
      dash: s.dash === 'dash' ? 'dash' : 'solid',
    },
    name: s.name,
    hovertemplate: `${s.name}: $%{y:,.2f}<extra></extra>`,
  }));
}

export function buildOverlayLayout(
  colors: ThemeColors,
  params: { chartTitle: string; yAxisLabel: string }
): PlotlyLayout {
  return {
    title: {
      text: params.chartTitle,
      font: { size: 16, color: colors.text },
    },
    xaxis: {
      type: 'date',
      gridcolor: colors.grid,
      tickfont: { color: colors.textMuted },
    },
    yaxis: {
      title: { text: params.yAxisLabel },
      side: 'right',
      gridcolor: colors.grid,
      tickfont: { color: colors.textMuted },
      titlefont: { color: colors.textMuted },
      tickformat: '$,.0f',
    },
    legend: {
      orientation: 'h',
      y: 1.12,
      x: 0.5,
      xanchor: 'center',
      font: { color: colors.textMuted },
    },
    margin: { t: 64, b: 40, l: 40, r: 72 },
    hovermode: 'x unified',
    paper_bgcolor: colors.paper,
    plot_bgcolor: colors.plot,
  };
}
