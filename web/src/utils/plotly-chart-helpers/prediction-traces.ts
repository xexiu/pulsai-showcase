/**
 * Prediction-dot scatter traces (per-candle model output) for the price panel.
 */

import {
  PREDICTION_MARKER_SIZE,
  PREDICTION_MARKER_STROKE_WIDTH,
  PREDICTION_OPACITY_ACTIONABLE,
  PREDICTION_OPACITY_HOLD,
} from '@/utils/plotly-chart-helpers/constants';
import { yForEntrySignalMarker } from '@/utils/plotly-chart-helpers/entry-signal-marker-y';
import type { CreatePredictionDataParams, PlotlyData } from '@/utils/plotly-chart-helpers/types';
import { mapTimestampForPlotlyTrace } from '@/utils/plotly-chart-time';

/**
 * Create prediction marker dots for per-candle model output.
 *
 * WHY small dots: Predictions are dense (one per candle). Large triangles
 * would clutter the chart. Small dots show the "cloud" of model predictions
 * while trade markers (triangles) show what the backtester actually did.
 *
 * Per plan: green=BUY, red=SELL, gray=HOLD (all three types).
 */
export function createPredictionData(params: CreatePredictionDataParams): PlotlyData | null {
  const { predictions, type, candles, colors, plotlyTime } = params;
  const candleMap = new Map(candles.map((c) => [c.timestamp, c]));

  const filtered = predictions.filter((p) => p.type === type);

  if (filtered.length === 0) {
    return null;
  }

  const isBuy = type === 'BUY';
  const isHold = type === 'HOLD';
  const yValues = filtered.map((p) => {
    const candle = candleMap.get(p.timestamp);

    if (candle === undefined) {
      return 0;
    }

    if (isHold) {
      return candle.close;
    }

    return yForEntrySignalMarker(candle, isBuy);
  });

  const hoverTexts = filtered.map(
    (p) => `Prediction: ${p.type}<br>Confidence: ${p.confidence.toFixed(1)}%`
  );

  let markerColor: string;

  if (isHold) {
    markerColor = colors.textMuted;
  } else if (isBuy) {
    markerColor = colors.bullish;
  } else {
    markerColor = colors.bearish;
  }

  return {
    type: 'scatter',
    mode: 'markers',
    name: `Pred ${type}`,
    xaxis: 'x',
    yaxis: 'y',
    x: filtered.map((p) => mapTimestampForPlotlyTrace(p.timestamp, plotlyTime)),
    y: yValues,
    marker: {
      symbol: 'circle',
      size: PREDICTION_MARKER_SIZE,
      color: markerColor,
      opacity: isHold ? PREDICTION_OPACITY_HOLD : PREDICTION_OPACITY_ACTIONABLE,
      line: { color: colors.paper, width: PREDICTION_MARKER_STROKE_WIDTH },
    },
    text: hoverTexts,
    hovertemplate: '%{text}<extra></extra>',
    showlegend: true,
  };
}
