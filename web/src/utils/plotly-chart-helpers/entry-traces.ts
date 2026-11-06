import {
  buildCompoundFillHoverText,
  type ChartHoverLabels,
  buildSignalEntryHoverText,
} from '@/utils/plotly-chart-helpers/chart-hover-labels';
import {
  BACKTEST_SIGNAL_MARKER_EXECUTION_NOTE,
  confidenceToOpacity,
  confidenceToPlotlyEntryMarkerSize,
} from '@/utils/plotly-chart-helpers/constants';
import { yForEntrySignalMarker } from '@/utils/plotly-chart-helpers/entry-signal-marker-y';
import { buildSignalMlHoverText } from '@/utils/plotly-chart-helpers/signal-ml-hover';
import type {
  CandleData,
  PlotlyData,
  SignalData,
  ThemeColors,
} from '@/utils/plotly-chart-helpers/types';
import { mapTimestampForPlotlyTrace, type PlotlyTimeOptions } from '@/utils/plotly-chart-time';

/** Options for enriched signal marker hover text. */
export type CreateSignalDataOptions = {
  candlesByTimestamp?: Map<string, CandleData>;
  chartMlModelHover?: boolean;
  hoverLabels?: ChartHoverLabels;
};

export function createSignalData(
  signals: SignalData[],
  type: 'BUY' | 'SELL',
  colors: ThemeColors,
  plotlyTime: PlotlyTimeOptions,
  options?: CreateSignalDataOptions
): PlotlyData | null {
  const filtered = signals.filter((s) => s.type === type && s.reason !== 'compound_fill');

  if (filtered.length === 0) {
    return null;
  }

  const isBuy = type === 'BUY';
  const candleMap = options?.candlesByTimestamp;
  const mlHover = options?.chartMlModelHover === true && candleMap != null;

  const hoverTexts = filtered.map((s) => {
    if (mlHover) {
      // Type / price / confidence only — model feature vectors stay out of Plotly hover.
      return buildSignalMlHoverText(s, null);
    }

    return buildSignalEntryHoverText(
      s,
      type,
      BACKTEST_SIGNAL_MARKER_EXECUTION_NOTE,
      options?.hoverLabels
    );
  });

  const yValues = filtered.map((s) => {
    if (candleMap) {
      const candle = candleMap.get(s.timestamp);

      if (candle) {
        return yForEntrySignalMarker(candle, isBuy);
      }
    }

    return s.price;
  });

  return {
    type: 'scatter',
    mode: 'markers',
    name: type,
    xaxis: 'x',
    yaxis: 'y',
    x: filtered.map((s) => mapTimestampForPlotlyTrace(s.timestamp, plotlyTime)),
    y: yValues,
    marker: {
      symbol: isBuy ? 'triangle-up' : 'triangle-down',
      size: filtered.map((s) => confidenceToPlotlyEntryMarkerSize(s.confidence)),
      color: isBuy ? colors.bullish : colors.bearish,
      opacity: filtered.map((s) => confidenceToOpacity(s.confidence)),
      line: { color: colors.paper, width: 1 },
    },
    text: hoverTexts,
    hovertemplate: '%{text}<extra></extra>',
  };
}

export function createCompoundFillData(
  signals: SignalData[],
  colors: ThemeColors,
  entryType: 'BUY' | 'SELL',
  plotlyTime: PlotlyTimeOptions,
  hoverLabels?: ChartHoverLabels
): PlotlyData | null {
  const filtered = signals.filter((s) => s.reason === 'compound_fill' && s.type === entryType);

  if (filtered.length === 0) {
    return null;
  }

  const isBuy = entryType === 'BUY';
  const hoverTexts = filtered.map((s) => buildCompoundFillHoverText(s, hoverLabels));

  return {
    type: 'scatter',
    mode: 'markers',
    name: isBuy ? 'DCA fill' : 'DCA fill (short)',
    xaxis: 'x',
    yaxis: 'y',
    x: filtered.map((s) => mapTimestampForPlotlyTrace(s.timestamp, plotlyTime)),
    y: filtered.map((s) => s.price),
    marker: {
      symbol: isBuy ? 'triangle-up' : 'triangle-down',
      size: 7,
      color: colors.signal,
      opacity: 0.9,
      line: { color: colors.paper, width: 1 },
    },
    text: hoverTexts,
    hovertemplate: '%{text}<extra></extra>',
  };
}
