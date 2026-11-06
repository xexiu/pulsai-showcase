import { describe, expect, it } from 'vitest';

import {
  buildHoverLabels,
  buildLayoutWithOverlays,
  buildTraces,
  resolveLastTimestamp,
} from '@/components/molecules/BacktestChart/useBacktestChartData.helpers';
import type { BuildTracesInput } from '@/components/molecules/BacktestChart/useBacktestChartData.types';
import { getThemeColors, type PlotlyShape } from '@/utils/plotly-chart-helpers';

import {
  BACKTEST_BUILD_TRACES_GUARD_MS,
  expectPerfBudgetMet,
  perfBudgetsEnforced,
} from '../../../../shared/perf-budgets';

/** Smoke path: smaller payload so default `pnpm test` stays fast and deterministic. */
const BUILD_TRACES_PERF_CANDLE_COUNT_SMOKE = 400;
const BUILD_TRACES_PERF_CANDLE_COUNT_FULL = 1200;
const BUILD_TRACES_PERF_ITERATIONS_SMOKE = 2;
const BUILD_TRACES_PERF_ITERATIONS_FULL = 5;

const CHART_LABELS: BuildTracesInput['chartLabels'] = {
  noData: 'No data',
  dynamicRegimeTraceNamePrefix: 'Dyn TP/SL vol',
  dynamicRegimeHoverEntryPrefix: 'Entry',
  dynamicRegimeHoverRegimeLabel: 'Dyn TP/SL vol band',
  dynamicRegimeLabelLow: 'Low',
  dynamicRegimeLabelMid: 'Medium',
  dynamicRegimeLabelHigh: 'High',
  hoverConfidence: 'Confidence',
  hoverEntryFee: 'Entry fee',
  hoverExitReason: 'Exit reason',
  hoverExitNetPnl: 'Net PnL',
  hoverExitFee: 'Exit fee',
  hoverStopLoss: 'Stop loss',
  hoverTakeProfit: 'Take profit',
  hoverDcaFill: 'DCA fill',
  hoverLong: 'Long',
  hoverShort: 'Short',
};

describe('useBacktestChartData.helpers', () => {
  it('maps chart labels into hover labels', () => {
    const labels = buildHoverLabels(CHART_LABELS);

    expect(labels).toEqual({
      confidence: 'Confidence',
      entryFee: 'Entry fee',
      exitReason: 'Exit reason',
      exitNetPnl: 'Net PnL',
      exitFee: 'Exit fee',
      stopLoss: 'Stop loss',
      takeProfit: 'Take profit',
      dcaFill: 'DCA fill',
      long: 'Long',
      short: 'Short',
    });
  });

  it('resolves last candle timestamp from canonical Candle[] (SignalChartCandle)', () => {
    expect(resolveLastTimestamp([])).toBeUndefined();
    expect(
      resolveLastTimestamp([
        { timestamp: '2026-01-01T00:00:00Z', open: 1, high: 2, low: 0.5, close: 1.5 },
      ])
    ).toBe('2026-01-01T00:00:00Z');
    expect(
      resolveLastTimestamp([
        { timestamp: '2026-01-01T00:00:00Z', open: 1, high: 2, low: 0.5, close: 1.5 },
        { timestamp: '2026-01-01T01:00:00Z', open: 1.5, high: 2.5, low: 1, close: 2 },
      ])
    ).toBe('2026-01-01T01:00:00Z');
  });

  it('adds TP/SL and 1R guide shapes to layout', () => {
    const colors = getThemeColors(true);
    const tpShape: PlotlyShape = {
      type: 'line',
      x0: '1',
      x1: '2',
      y0: 100,
      y1: 100,
      xref: 'x',
      yref: 'y',
    };
    const rShape: PlotlyShape = {
      type: 'line',
      x0: '1',
      x1: '2',
      y0: 110,
      y1: 110,
      xref: 'x',
      yref: 'y',
    };
    const layout = buildLayoutWithOverlays({
      symbol: 'BTCUSDT',
      timeframe: '1h',
      showEquityCurve: false,
      hasRSI: false,
      hasMACD: false,
      colors,
      chartDisplayTimezone: 'UTC',
      chartHeight: 520,
      tpSlShapes: [tpShape],
      rGuideShapes: [rShape],
      liquidationGuideShapes: [],
      liquidationHeatmapShapes: [],
    });

    const shapes = Array.isArray(layout['shapes']) ? layout['shapes'] : [];

    expect(layout['height']).toBe(520);
    expect(shapes).toEqual(expect.arrayContaining([tpShape, rShape]));
  });

  it('builds traces with dynamic regime labels from chart labels', () => {
    const colors = getThemeColors(true);
    const traces = buildTraces({
      candles: [{ timestamp: '2026-01-01T00:00:00Z', open: 100, high: 110, low: 95, close: 105 }],
      signals: [
        {
          timestamp: '2026-01-01T00:00:00Z',
          type: 'BUY',
          price: 100,
          confidence: 70,
          dynamic_volatility_regime: 'low',
        },
      ],
      predictions: undefined,
      equityCurve: undefined,
      showEquityCurve: false,
      colors,
      plotlyTime: { chartTimezone: 'UTC', timeframe: '1h' },
      rsi: undefined,
      macd: undefined,
      bollingerBands: undefined,
      hasRSI: false,
      hasMACD: false,
      chartMlModelHover: false,
      showDynamicRegimeHints: true,
      chartLabels: CHART_LABELS,
    });

    const regimeTrace = traces.find((trace) => trace['name'] === 'Dyn TP/SL vol: Low');

    expect(regimeTrace).toBeDefined();
    const regimeText = regimeTrace?.['text'] as string[];
    const firstText = Array.isArray(regimeText) ? String(regimeText[0]) : '';

    expect(firstText).toContain('Dyn TP/SL vol band');
  });

  it(
    'buildTraces stays under perf guard for representative backtest payload',
    () => {
      const fullBench = perfBudgetsEnforced();
      const colors = getThemeColors(true);
      const n = fullBench
        ? BUILD_TRACES_PERF_CANDLE_COUNT_FULL
        : BUILD_TRACES_PERF_CANDLE_COUNT_SMOKE;
      const signalStride = fullBench ? 6 : 10;
      const iterations = fullBench
        ? BUILD_TRACES_PERF_ITERATIONS_FULL
        : BUILD_TRACES_PERF_ITERATIONS_SMOKE;
      const candles = Array.from({ length: n }, (_, i) => ({
        timestamp: new Date(Date.UTC(2026, 0, 1, i)).toISOString(),
        open: 100 + i * 0.1,
        high: 101 + i * 0.1,
        low: 99 + i * 0.1,
        close: 100.5 + i * 0.1,
      }));
      const signalCount = Math.max(1, Math.floor(n / signalStride));
      const signals = Array.from({ length: signalCount }, (_, i) => ({
        timestamp: candles[i * signalStride]!.timestamp,
        type: i % 2 === 0 ? ('BUY' as const) : ('SELL' as const),
        price: candles[i * signalStride]!.close,
        confidence: 70,
        dynamic_volatility_regime:
          // eslint-disable-next-line no-nested-ternary
          i % 3 === 0 ? ('low' as const) : i % 3 === 1 ? ('mid' as const) : ('high' as const),
      }));
      const input: BuildTracesInput = {
        candles,
        signals,
        predictions: undefined,
        equityCurve: undefined,
        showEquityCurve: false,
        colors,
        plotlyTime: { chartTimezone: 'UTC', timeframe: '1h' },
        rsi: undefined,
        macd: undefined,
        bollingerBands: undefined,
        hasRSI: false,
        hasMACD: false,
        chartMlModelHover: false,
        showDynamicRegimeHints: true,
        chartLabels: CHART_LABELS,
      };

      buildTraces(input); // warmup
      const samples: number[] = [];

      for (let i = 0; i < iterations; i += 1) {
        const t0 = performance.now();

        buildTraces(input);
        samples.push(performance.now() - t0);
      }
      const sorted = [...samples].sort((a, b) => a - b);
      const medianMs = sorted[Math.floor(sorted.length / 2)]!;

      // Assertion is gated on PULSAI_PERF_BUDGETS=1 — see perf-budgets.ts for
      // rationale. Without enforcement the test still runs (covers the code
      // path) but the numeric budget is informational only, eliminating flakes
      // from environmental wall-clock variance on shared/CI runners.
      expectPerfBudgetMet(medianMs, BACKTEST_BUILD_TRACES_GUARD_MS, 'buildTraces', expect);
    },
    perfBudgetsEnforced() ? 60_000 : 15_000
  );
});
