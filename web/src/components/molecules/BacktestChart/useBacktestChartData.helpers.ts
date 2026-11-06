import { appendPredictionDotTraces } from '@/components/molecules/BacktestChart/appendPredictionDotTraces';
import type {
  BacktestLayoutInput,
  BuildHoverLabelsInput,
  BuildHoverLabelsOutput,
  BuildTracesInput,
} from '@/components/molecules/BacktestChart/useBacktestChartData.types';
import type { PlotlyLayout } from '@/types/plotly-layout';
import { SIGNAL_ACTIONS } from '@/utils/constants';
import {
  createCandlestickData,
  createCompoundFillData,
  createDynamicRegimeHintData,
  createEquityData,
  createExitData,
  createSignalData,
  type LayoutOptions,
  type PlotlyData,
} from '@/utils/plotly-chart-helpers';
import { createChartLayout, parsePlotlyLayoutShapes } from '@/utils/plotly-chart-layout';
import {
  createBollingerBandsData,
  createMACDData,
  createRSIData,
} from '@/utils/plotly-indicator-helpers';

export function buildHoverLabels(chartLabels: BuildHoverLabelsInput): BuildHoverLabelsOutput {
  return {
    confidence: chartLabels.hoverConfidence,
    entryFee: chartLabels.hoverEntryFee,
    exitReason: chartLabels.hoverExitReason,
    exitNetPnl: chartLabels.hoverExitNetPnl,
    exitFee: chartLabels.hoverExitFee,
    stopLoss: chartLabels.hoverStopLoss,
    takeProfit: chartLabels.hoverTakeProfit,
    dcaFill: chartLabels.hoverDcaFill,
    long: chartLabels.hoverLong,
    short: chartLabels.hoverShort,
  };
}

/** Last bar timestamp for overlay x-end (canonical candles carry ISO `timestamp`). */
export function resolveLastTimestamp(candles: BuildTracesInput['candles']): string | undefined {
  return candles.at(-1)?.timestamp;
}

export function buildLayoutWithOverlays(params: BacktestLayoutInput): PlotlyLayout {
  const opts: LayoutOptions = {
    symbol: params.symbol,
    timeframe: params.timeframe,
    showEquityCurve: params.showEquityCurve,
    hasRSI: params.hasRSI,
    hasMACD: params.hasMACD,
    colors: params.colors,
  };

  if (params.chartDisplayTimezone !== undefined) {
    opts.chartDisplayTimezone = params.chartDisplayTimezone;
  }
  if (params.chartHeight !== undefined) {
    opts.chartHeight = params.chartHeight;
  }

  const base = createChartLayout(opts);

  if (
    params.tpSlShapes.length === 0 &&
    params.rGuideShapes.length === 0 &&
    params.liquidationGuideShapes.length === 0 &&
    params.liquidationHeatmapShapes.length === 0
  ) {
    return base;
  }
  const existingShapes = parsePlotlyLayoutShapes(base['shapes']);

  return {
    ...base,
    shapes: [
      ...existingShapes,
      ...params.tpSlShapes,
      ...params.rGuideShapes,
      ...params.liquidationGuideShapes,
      ...params.liquidationHeatmapShapes,
    ],
  };
}

export function buildTraces(t: BuildTracesInput): PlotlyData[] {
  const result: PlotlyData[] = [];

  result.push(...createBollingerBandsData(t.bollingerBands, t.colors, t.plotlyTime));

  const candlestick = createCandlestickData(t.candles, t.colors, t.plotlyTime, {
    chartMlModelHover: t.chartMlModelHover,
  });

  if (candlestick) result.push(candlestick);

  if (t.predictions && t.predictions.length > 0) {
    appendPredictionDotTraces(result, {
      predictions: t.predictions,
      candles: t.candles,
      colors: t.colors,
      plotlyTime: t.plotlyTime,
      chartMlModelHover: t.chartMlModelHover,
    });
  }

  const candleMap = new Map(t.candles.map((c) => [c.timestamp, c]));
  const signalOpts = { candlesByTimestamp: candleMap, chartMlModelHover: t.chartMlModelHover };
  const hoverLabels = buildHoverLabels(t.chartLabels);
  const signalOptsWithLabels = { ...signalOpts, hoverLabels };

  const buy = createSignalData(
    t.signals,
    SIGNAL_ACTIONS.BUY,
    t.colors,
    t.plotlyTime,
    signalOptsWithLabels
  );
  const sell = createSignalData(
    t.signals,
    SIGNAL_ACTIONS.SELL,
    t.colors,
    t.plotlyTime,
    signalOptsWithLabels
  );
  const cBuy = createCompoundFillData(
    t.signals,
    t.colors,
    SIGNAL_ACTIONS.BUY,
    t.plotlyTime,
    hoverLabels
  );
  const cSell = createCompoundFillData(
    t.signals,
    t.colors,
    SIGNAL_ACTIONS.SELL,
    t.plotlyTime,
    hoverLabels
  );
  const exits = createExitData(t.signals, t.colors, t.plotlyTime, hoverLabels);
  const dynamicRegimeHints = createDynamicRegimeHintData(
    t.signals,
    t.colors,
    t.plotlyTime,
    t.showDynamicRegimeHints,
    {
      traceNamePrefix: t.chartLabels.dynamicRegimeTraceNamePrefix,
      hoverEntryPrefix: t.chartLabels.dynamicRegimeHoverEntryPrefix,
      hoverRegimeLabel: t.chartLabels.dynamicRegimeHoverRegimeLabel,
      regimeLabels: {
        low: t.chartLabels.dynamicRegimeLabelLow,
        mid: t.chartLabels.dynamicRegimeLabelMid,
        high: t.chartLabels.dynamicRegimeLabelHigh,
      },
    }
  );

  if (buy) result.push(buy);
  if (cBuy) result.push(cBuy);
  if (sell) result.push(sell);
  if (cSell) result.push(cSell);
  if (exits) result.push(exits);
  result.push(...dynamicRegimeHints);

  const equity = createEquityData(t.equityCurve, t.showEquityCurve, t.colors, t.plotlyTime);

  if (equity) result.push(equity);
  if (t.hasRSI) result.push(...createRSIData(t.rsi, t.colors, t.plotlyTime));
  if (t.hasMACD) result.push(...createMACDData(t.macd, t.colors, t.plotlyTime));

  return result;
}
