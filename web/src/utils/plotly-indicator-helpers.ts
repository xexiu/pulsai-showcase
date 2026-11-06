/**
 * Plotly Indicator Data Creators (extracted for max-lines compliance)
 *
 * WHY SEPARATE: plotly-chart-helpers.ts exceeded 400-line limit.
 * SRP: Indicator-specific trace creation (RSI, MACD, Bollinger Bands).
 *
 * @see docs/04-structural/CODING_STANDARDS.md Section 7.2
 */

import {
  RSI_OVERBOUGHT,
  RSI_OVERSOLD,
  type BBData,
  type MACDData,
  type PlotlyData,
  type RSIData,
  type ThemeColors,
} from '@/utils/plotly-chart-helpers';
import { mapTimestampForPlotlyTrace, type PlotlyTimeOptions } from '@/utils/plotly-chart-time';

export function createRSIData(
  rsi: RSIData | undefined,
  colors: ThemeColors,
  plotlyTime: PlotlyTimeOptions
): PlotlyData[] {
  if (!rsi || rsi.length === 0) {
    return [];
  }

  const first = rsi.at(0);
  const last = rsi.at(-1);

  if (first == null || last == null) {
    return [];
  }

  const timeRange = [
    mapTimestampForPlotlyTrace(first.timestamp, plotlyTime),
    mapTimestampForPlotlyTrace(last.timestamp, plotlyTime),
  ];

  return [
    {
      type: 'scatter',
      mode: 'lines',
      name: 'RSI',
      xaxis: 'x',
      yaxis: 'y3',
      x: rsi.map((r) => mapTimestampForPlotlyTrace(r.timestamp, plotlyTime)),
      y: rsi.map((r) => r.value),
      line: { color: colors.signal, width: 1.5 },
      hovertemplate: 'RSI: %{y:.1f}<extra></extra>',
    },
    {
      type: 'scatter',
      mode: 'lines',
      name: 'Overbought',
      showlegend: false,
      xaxis: 'x',
      yaxis: 'y3',
      x: timeRange,
      y: [RSI_OVERBOUGHT, RSI_OVERBOUGHT],
      line: { color: colors.bearish, width: 1, dash: 'dot' },
    },
    {
      type: 'scatter',
      mode: 'lines',
      name: 'Oversold',
      showlegend: false,
      xaxis: 'x',
      yaxis: 'y3',
      x: timeRange,
      y: [RSI_OVERSOLD, RSI_OVERSOLD],
      line: { color: colors.bullish, width: 1, dash: 'dot' },
    },
  ];
}

export function createMACDData(
  macd: MACDData | undefined,
  colors: ThemeColors,
  plotlyTime: PlotlyTimeOptions
): PlotlyData[] {
  if (!macd || macd.length === 0) {
    return [];
  }

  return [
    {
      type: 'scatter',
      mode: 'lines',
      name: 'MACD',
      xaxis: 'x',
      yaxis: 'y4',
      x: macd.map((m) => mapTimestampForPlotlyTrace(m.timestamp, plotlyTime)),
      y: macd.map((m) => m.macd),
      line: { color: '#3b82f6', width: 1.5 },
    },
    {
      type: 'scatter',
      mode: 'lines',
      name: 'Signal',
      xaxis: 'x',
      yaxis: 'y4',
      x: macd.map((m) => mapTimestampForPlotlyTrace(m.timestamp, plotlyTime)),
      y: macd.map((m) => m.signal),
      line: { color: '#f97316', width: 1.5 },
    },
    {
      type: 'bar',
      name: 'Histogram',
      showlegend: false,
      xaxis: 'x',
      yaxis: 'y4',
      x: macd.map((m) => mapTimestampForPlotlyTrace(m.timestamp, plotlyTime)),
      y: macd.map((m) => m.histogram),
      marker: {
        color: macd.map((m) => (m.histogram >= 0 ? colors.bullish : colors.bearish)),
      },
    },
  ];
}

export function createBollingerBandsData(
  bb: BBData | undefined,
  colors: ThemeColors,
  plotlyTime: PlotlyTimeOptions
): PlotlyData[] {
  if (!bb || bb.length === 0) {
    return [];
  }

  return [
    {
      type: 'scatter',
      mode: 'lines',
      name: 'BB Upper',
      showlegend: false,
      xaxis: 'x',
      yaxis: 'y',
      x: bb.map((b) => mapTimestampForPlotlyTrace(b.timestamp, plotlyTime)),
      y: bb.map((b) => b.upper),
      line: { color: colors.textMuted, width: 1 },
    },
    {
      type: 'scatter',
      mode: 'lines',
      name: 'BB Middle',
      showlegend: false,
      xaxis: 'x',
      yaxis: 'y',
      x: bb.map((b) => mapTimestampForPlotlyTrace(b.timestamp, plotlyTime)),
      y: bb.map((b) => b.middle),
      line: { color: colors.signal, width: 1, dash: 'dot' },
    },
    {
      type: 'scatter',
      mode: 'lines',
      name: 'BB Lower',
      showlegend: false,
      xaxis: 'x',
      yaxis: 'y',
      fill: 'tonexty',
      fillcolor: 'rgba(124, 77, 255, 0.1)',
      x: bb.map((b) => mapTimestampForPlotlyTrace(b.timestamp, plotlyTime)),
      y: bb.map((b) => b.lower),
      line: { color: colors.textMuted, width: 1 },
    },
  ];
}
