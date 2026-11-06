/**
 * Appends BUY/SELL/HOLD prediction scatter traces to the main price panel.
 *
 * WHY extracted: keeps `useBacktestChartData` under eslint max-lines / complexity.
 */

import type { Candle, Prediction } from '@/components/molecules/BacktestChart/types';
import { SIGNAL_ACTIONS } from '@/utils/constants';
import {
  createPredictionData,
  type PlotlyData,
  type ThemeColors,
} from '@/utils/plotly-chart-helpers';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

export function appendPredictionDotTraces(
  result: PlotlyData[],
  params: {
    predictions: Prediction[];
    candles: Candle[];
    colors: ThemeColors;
    plotlyTime: PlotlyTimeOptions;
    chartMlModelHover?: boolean;
  }
): void {
  const { predictions, candles, colors, plotlyTime, chartMlModelHover } = params;

  if (predictions.length === 0) {
    return;
  }

  const candleData = candles.map((c) => ({
    timestamp: c.timestamp,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));

  const predictionArgs = {
    predictions,
    candles: candleData,
    colors,
    plotlyTime,
    ...(chartMlModelHover !== undefined ? { chartMlModelHover } : {}),
  };

  const buyPreds = createPredictionData({
    ...predictionArgs,
    type: SIGNAL_ACTIONS.BUY,
  });
  const sellPreds = createPredictionData({
    ...predictionArgs,
    type: SIGNAL_ACTIONS.SELL,
  });
  const holdPreds = createPredictionData({
    ...predictionArgs,
    type: SIGNAL_ACTIONS.HOLD,
  });

  if (buyPreds) result.push(buyPreds);
  if (sellPreds) result.push(sellPreds);
  if (holdPreds) result.push(holdPreds);
}
