import { SIGNAL_ACTIONS } from '@/utils/constants/core';
import { formatPrice } from '@/utils/formatters';
import {
  DYNAMIC_REGIME_HINT_MARKER_OPACITY,
  DYNAMIC_REGIME_HINT_MARKER_SIZE,
  DYNAMIC_REGIME_HINT_MARKER_STROKE_WIDTH,
} from '@/utils/plotly-chart-helpers/constants';
import {
  DYNAMIC_VOLATILITY_REGIME_ORDER,
  getDynamicVolatilityRegimeColor,
  type DynamicVolatilityRegime,
  toDynamicVolatilityRegime,
} from '@/utils/plotly-chart-helpers/dynamic-regime';
import type { PlotlyData, SignalData, ThemeColors } from '@/utils/plotly-chart-helpers/types';
import { mapTimestampForPlotlyTrace, type PlotlyTimeOptions } from '@/utils/plotly-chart-time';

export type DynamicRegimeTraceLabels = {
  traceNamePrefix: string;
  hoverEntryPrefix: string;
  hoverRegimeLabel: string;
  regimeLabels?: Partial<Record<DynamicVolatilityRegime, string>>;
};

const REGIME_MARKER_SYMBOL: Record<DynamicVolatilityRegime, string> = {
  low: 'circle',
  mid: 'diamond',
  high: 'square',
};

function displayRegimeLabel(
  regime: DynamicVolatilityRegime,
  labels: DynamicRegimeTraceLabels
): string {
  return labels.regimeLabels?.[regime] ?? regime;
}

export function createDynamicRegimeHintData(
  signals: SignalData[],
  colors: ThemeColors,
  plotlyTime: PlotlyTimeOptions,
  enabled: boolean,
  labels: DynamicRegimeTraceLabels
): PlotlyData[] {
  if (!enabled) {
    return [];
  }

  const entriesByRegime: Record<'low' | 'mid' | 'high', SignalData[]> = {
    low: [],
    mid: [],
    high: [],
  };

  for (const signal of signals) {
    if (signal.type !== SIGNAL_ACTIONS.BUY && signal.type !== SIGNAL_ACTIONS.SELL) {
      continue;
    }
    const regime = toDynamicVolatilityRegime(signal.dynamic_volatility_regime);

    if (regime === null) {
      continue;
    }
    entriesByRegime[regime].push(signal);
  }

  const traces: PlotlyData[] = [];

  for (const regime of DYNAMIC_VOLATILITY_REGIME_ORDER) {
    const regimeEntries = entriesByRegime[regime];

    if (regimeEntries.length === 0) {
      continue;
    }

    traces.push({
      type: 'scatter',
      mode: 'markers',
      name: `${labels.traceNamePrefix}: ${displayRegimeLabel(regime, labels)}`,
      xaxis: 'x',
      yaxis: 'y',
      x: regimeEntries.map((signal) => mapTimestampForPlotlyTrace(signal.timestamp, plotlyTime)),
      y: regimeEntries.map((signal) => signal.price),
      marker: {
        symbol: REGIME_MARKER_SYMBOL[regime],
        size: DYNAMIC_REGIME_HINT_MARKER_SIZE,
        color: getDynamicVolatilityRegimeColor(regime, colors),
        opacity: DYNAMIC_REGIME_HINT_MARKER_OPACITY,
        line: { color: colors.paper, width: DYNAMIC_REGIME_HINT_MARKER_STROKE_WIDTH },
      },
      text: regimeEntries.map(
        (signal) =>
          `${labels.hoverEntryPrefix} @ ${formatPrice(signal.price)}<br>${labels.hoverRegimeLabel}: ${displayRegimeLabel(regime, labels)}`
      ),
      hovertemplate: '%{text}<extra></extra>',
    });
  }

  return traces;
}
