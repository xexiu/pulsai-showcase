// @vitest-environment node
/**
 * plotly-chart-helpers Utility Tests
 *
 * WHY: Constructs Plotly chart data/layout for training visualization
 *
 * @see docs/04-structural/CODING_STANDARDS.md - TDD requirements
 */

import { describe, expect, it } from 'vitest';

/** Drill into Plotly trace/layout objects in tests without `any`. */
function plotlyDeep(obj: unknown, ...path: string[]): unknown {
  let cur: unknown = obj;

  for (const key of path) {
    cur = (cur as Record<string, unknown>)[key];
  }

  return cur;
}

import {
  createDynamicRegimeHintData,
  createEquityData,
  createExitData,
  createRLevelGuideShapes,
  getThemeColors,
  type BBData,
  type EquityData,
  type MACDData,
  type RSIData,
  type SignalData,
} from '@/utils/plotly-chart-helpers';
import { resolveEntryActiveWindow } from '@/utils/plotly-chart-helpers/entry-active-window';
import {
  createChartLayout,
  createPlotlyChartConfig,
  formatBacktestPlotlyXAxisTitle,
} from '@/utils/plotly-chart-layout';
import {
  createBollingerBandsData,
  createMACDData,
  createRSIData,
} from '@/utils/plotly-indicator-helpers';

/** Plotly x: real UTC epoch ms (chartTimezone unused; kept for PlotlyTimeOptions shape). */
const PLOTLY_UTC_1H = { chartTimezone: 'UTC', timeframe: '1h' } as const;
const REGIME_TRACE_LABELS = {
  traceNamePrefix: 'Dyn TP/SL vol',
  hoverEntryPrefix: 'Entry',
  hoverRegimeLabel: 'Dyn TP/SL vol band',
} as const;

const mockSignals: SignalData[] = [
  { timestamp: '2026-01-01T00:00:00Z', type: 'BUY', price: 100, confidence: 85 },
  { timestamp: '2026-01-01T01:00:00Z', type: 'SELL', price: 110, confidence: 75 },
];

describe('plotly-chart-helpers (exit + layout)', () => {
  describe('createExitData', () => {
    it('creates EXIT markers with bearish color for long side (sell-to-close)', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'EXIT', price: 110, side: 'long' },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(plotlyDeep(trace, 'marker', 'color')).toEqual([colors.bearish]);
    });

    it('creates EXIT markers with bullish color for short side (buy-to-close)', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'EXIT', price: 108, side: 'short' },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(plotlyDeep(trace, 'marker', 'color')).toEqual([colors.bullish]);
    });

    it('uses bearish color when side is missing (backward compatibility)', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'EXIT', price: 110 },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(plotlyDeep(trace, 'marker', 'color')).toEqual([colors.bearish]);
    });

    it('returns null when no EXIT signals', () => {
      const colors = getThemeColors(true);
      const trace = createExitData(mockSignals, colors, PLOTLY_UTC_1H);

      expect(trace).toBeNull();
    });

    it('hover includes net_pnl and exit_fee when present (Chart DRY plan)', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        {
          timestamp: '2026-01-01T01:00:00Z',
          type: 'EXIT',
          price: 51000,
          reason: 'holding_period',
          side: 'long',
          net_pnl: 95.5,
          exit_fee: 1.02,
        },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('EXIT @ $51,000.00');
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Reason: holding_period');
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Net PnL: $95.50');
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Exit Fee: $1.02');
    });

    it('hover includes stop_loss and take_profit when present', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        {
          timestamp: '2026-01-01T01:00:00Z',
          type: 'EXIT',
          price: 51000,
          reason: 'take_profit',
          side: 'long',
          net_pnl: 200,
          stop_loss: 49000,
          take_profit: 51000,
        },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Stop Loss: $49,000.00');
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Take Profit: $51,000.00');
    });

    it('uses bullish color when net_pnl > 0 (PnL-based coloring)', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          type: 'EXIT',
          price: 110,
          side: 'long',
          net_pnl: 5.5,
        },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(plotlyDeep(trace, 'marker', 'color')).toEqual([colors.bullish]);
    });

    it('uses bearish color when net_pnl < 0 (PnL-based coloring)', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          type: 'EXIT',
          price: 95,
          side: 'short',
          net_pnl: -3.2,
        },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(plotlyDeep(trace, 'marker', 'color')).toEqual([colors.bearish]);
    });

    it('uses textMuted (grey) when net_pnl === 0 (break-even)', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          type: 'EXIT',
          price: 100,
          side: 'long',
          net_pnl: 0,
        },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(plotlyDeep(trace, 'marker', 'color')).toEqual([colors.textMuted]);
    });

    it('falls back to side-based color when net_pnl is missing', () => {
      const colors = getThemeColors(true);
      const longExit: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'EXIT', price: 110, side: 'long' },
      ];
      const shortExit: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'EXIT', price: 90, side: 'short' },
      ];

      expect(
        plotlyDeep(createExitData(longExit, colors, PLOTLY_UTC_1H), 'marker', 'color')
      ).toEqual([colors.bearish]);
      expect(
        plotlyDeep(createExitData(shortExit, colors, PLOTLY_UTC_1H), 'marker', 'color')
      ).toEqual([colors.bullish]);
    });

    it('uses injected localized hover labels for EXIT traces', () => {
      const colors = getThemeColors(true);
      const exitSignals: SignalData[] = [
        {
          timestamp: '2026-01-01T01:00:00Z',
          type: 'EXIT',
          price: 51000,
          reason: 'take_profit',
          side: 'long',
          net_pnl: 95.5,
          exit_fee: 1.02,
        },
      ];
      const trace = createExitData(exitSignals, colors, PLOTLY_UTC_1H, {
        confidence: 'Confianza:',
        entryFee: 'Comisión de entrada:',
        exitReason: 'Motivo:',
        exitNetPnl: 'PnL neto:',
        exitFee: 'Comisión de salida:',
        stopLoss: 'Stop Loss:',
        takeProfit: 'Take Profit:',
        dcaFill: 'Relleno DCA',
        long: 'Largo',
        short: 'Corto',
      });

      expect(trace).not.toBeNull();
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Motivo: take_profit');
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('PnL neto: $95.50');
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Comisión de salida: $1.02');
    });
  });

  describe('createEquityData', () => {
    it('creates equity curve trace when show=true', () => {
      const equityData: EquityData[] = [
        { timestamp: '2026-01-01T00:00:00Z', value: 10000 },
        { timestamp: '2026-01-01T01:00:00Z', value: 10500 },
      ];
      const colors = getThemeColors(true);
      const trace = createEquityData(equityData, true, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(trace!.type).toBe('scatter');
      expect(trace!['mode']).toBe('lines');
      expect(trace!['y']).toEqual([10000, 10500]);
      expect(trace!['yaxis']).toBe('y2');
    });

    it('returns null when show=false', () => {
      const equityData: EquityData[] = [{ timestamp: '2026-01-01T00:00:00Z', value: 10000 }];
      const colors = getThemeColors(true);
      const trace = createEquityData(equityData, false, colors, PLOTLY_UTC_1H);

      expect(trace).toBeNull();
    });

    it('returns null when equity is empty', () => {
      const colors = getThemeColors(true);
      const trace = createEquityData([], true, colors, PLOTLY_UTC_1H);

      expect(trace).toBeNull();
    });
  });

  describe('createRLevelGuideShapes', () => {
    it('creates 1R and minTP guide lines for long entries when enabled', () => {
      const guides = createRLevelGuideShapes(
        [
          {
            timestamp: '2026-01-01T00:00:00Z',
            type: 'BUY',
            side: 'long',
            price: 100,
            stop_loss_price: 95,
            take_profit_price: 108,
          },
        ],
        true,
        PLOTLY_UTC_1H,
        '2026-01-01T02:00:00Z'
      );

      expect(guides).toHaveLength(2);
      expect(guides[0]?.type).toBe('line');
      expect(guides[0]?.y0).toBe(105); // 1R above entry for long
      expect(guides[1]?.y0).toBe(108); // minTP = configured TP
      expect(typeof guides[0]?.x0).toBe('number');
    });

    it('returns empty when disabled', () => {
      const guides = createRLevelGuideShapes(
        [
          {
            timestamp: '2026-01-01T00:00:00Z',
            type: 'SELL',
            side: 'short',
            price: 100,
            stop_loss_price: 103,
            take_profit_price: 94,
          },
        ],
        false,
        PLOTLY_UTC_1H,
        '2026-01-01T02:00:00Z'
      );

      expect(guides).toEqual([]);
    });

    it('accepts stop/tp aliases when stop_loss_price/take_profit_price are absent', () => {
      const guides = createRLevelGuideShapes(
        [
          {
            timestamp: '2026-01-01T00:00:00Z',
            type: 'BUY',
            side: 'long',
            price: 100,
            stop_loss: 95,
            take_profit: 108,
          },
        ],
        true,
        PLOTLY_UTC_1H,
        '2026-01-01T02:00:00Z'
      );

      expect(guides).toHaveLength(2);
    });
  });

  describe('createDynamicRegimeHintData', () => {
    it('creates regime hint marker traces for entry signals when enabled', () => {
      const colors = getThemeColors(true);
      const traces = createDynamicRegimeHintData(
        [
          {
            timestamp: '2026-01-01T00:00:00Z',
            type: 'BUY',
            price: 100,
            dynamic_volatility_regime: 'low',
          },
          {
            timestamp: '2026-01-01T01:00:00Z',
            type: 'SELL',
            price: 95,
            dynamic_volatility_regime: 'high',
          },
        ],
        colors,
        PLOTLY_UTC_1H,
        true,
        REGIME_TRACE_LABELS
      );

      expect(traces).toHaveLength(2);
      // Trace name = `${traceNamePrefix}: ${regime}` where the fixture prefix is 'Dyn TP/SL vol'.
      expect(traces[0]!['name']).toContain('Dyn TP/SL vol:');
      expect(traces[1]!['name']).toContain('Dyn TP/SL vol:');
    });

    it('returns empty when disabled', () => {
      const colors = getThemeColors(true);
      const traces = createDynamicRegimeHintData(
        [
          {
            timestamp: '2026-01-01T00:00:00Z',
            type: 'BUY',
            price: 100,
            dynamic_volatility_regime: 'mid',
          },
        ],
        colors,
        PLOTLY_UTC_1H,
        false,
        REGIME_TRACE_LABELS
      );

      expect(traces).toEqual([]);
    });

    it('accepts uppercase dynamic_volatility_regime labels', () => {
      const colors = getThemeColors(true);
      const traces = createDynamicRegimeHintData(
        [
          {
            timestamp: '2026-01-01T00:00:00Z',
            type: 'BUY',
            price: 100,
            dynamic_volatility_regime: 'HIGH',
          },
        ],
        colors,
        PLOTLY_UTC_1H,
        true,
        REGIME_TRACE_LABELS
      );

      expect(traces).toHaveLength(1);
      expect(String(traces[0]!['name'])).toContain('high');
    });

    it('does not rely on repeated filter passes for grouping', () => {
      const colors = getThemeColors(true);
      const signals: SignalData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          type: 'BUY',
          price: 100,
          dynamic_volatility_regime: 'low',
        },
        {
          timestamp: '2026-01-01T01:00:00Z',
          type: 'SELL',
          price: 101,
          dynamic_volatility_regime: 'mid',
        },
        {
          timestamp: '2026-01-01T02:00:00Z',
          type: 'BUY',
          price: 102,
          dynamic_volatility_regime: 'high',
        },
      ];
      const originalFilter = Array.prototype.filter;
      let filterCalls = 0;

      Array.prototype.filter = function (...args: Parameters<Array<unknown>['filter']>) {
        filterCalls += 1;

        return originalFilter.apply(this, args);
      };

      try {
        createDynamicRegimeHintData(signals, colors, PLOTLY_UTC_1H, true, REGIME_TRACE_LABELS);
      } finally {
        Array.prototype.filter = originalFilter;
      }

      expect(filterCalls).toBeLessThanOrEqual(2);
    });
  });

  describe('resolveEntryActiveWindow', () => {
    it('uses first matching EXIT timestamp when present', () => {
      const windowRange = resolveEntryActiveWindow(
        {
          timestamp: '2026-01-01T00:00:00Z',
          side: 'long',
        },
        [
          { timestamp: '2026-01-01T00:00:00Z', type: 'BUY', side: 'long', price: 100 },
          { timestamp: '2026-01-01T01:00:00Z', type: 'EXIT', side: 'short', price: 99 },
          { timestamp: '2026-01-01T02:00:00Z', type: 'EXIT', side: 'long', price: 101 },
        ],
        PLOTLY_UTC_1H,
        '2026-01-01T03:00:00Z'
      );

      expect(typeof windowRange.x0).toBe('number');
      expect(typeof windowRange.x1).toBe('number');
    });

    it('falls back to provided end timestamp when no EXIT exists', () => {
      const windowRange = resolveEntryActiveWindow(
        {
          timestamp: '2026-01-01T00:00:00Z',
          side: 'long',
        },
        [{ timestamp: '2026-01-01T00:00:00Z', type: 'BUY', side: 'long', price: 100 }],
        PLOTLY_UTC_1H,
        '2026-01-01T03:00:00Z'
      );

      expect(typeof windowRange.x1).toBe('number');
    });
  });

  describe('createRSIData', () => {
    it('creates RSI traces array (line + overbought/oversold)', () => {
      const rsiData: RSIData = [
        { timestamp: '2026-01-01T00:00:00Z', value: 30 },
        { timestamp: '2026-01-01T01:00:00Z', value: 70 },
      ];
      const colors = getThemeColors(true);
      const traces = createRSIData(rsiData, colors, PLOTLY_UTC_1H);

      expect(traces).toHaveLength(3);
      expect(traces[0]!['name']).toBe('RSI');
      expect(traces[0]!['type']).toBe('scatter');
      expect(traces[0]!['yaxis']).toBe('y3');
      expect(traces[1]!['name']).toBe('Overbought');
      expect(traces[2]!['name']).toBe('Oversold');
    });

    it('returns empty array for empty/undefined RSI', () => {
      const colors = getThemeColors(true);

      expect(createRSIData([], colors, PLOTLY_UTC_1H)).toEqual([]);
      expect(createRSIData(undefined, colors, PLOTLY_UTC_1H)).toEqual([]);
    });
  });

  describe('createMACDData', () => {
    it('creates MACD traces (line, signal, histogram)', () => {
      const macdData: MACDData = [
        { timestamp: '2026-01-01T00:00:00Z', macd: 0.5, signal: 0.3, histogram: 0.2 },
        { timestamp: '2026-01-01T01:00:00Z', macd: 0.8, signal: 0.5, histogram: 0.3 },
      ];
      const colors = getThemeColors(true);
      const traces = createMACDData(macdData, colors, PLOTLY_UTC_1H);

      expect(traces).toHaveLength(3);
      expect(traces[0]!['name']).toBe('MACD');
      expect(traces[1]!['name']).toBe('Signal');
      expect(traces[2]!['name']).toBe('Histogram');
      expect(traces[2]!['type']).toBe('bar');
    });

    it('returns empty array for empty/undefined MACD', () => {
      const colors = getThemeColors(true);

      expect(createMACDData([], colors, PLOTLY_UTC_1H)).toEqual([]);
      expect(createMACDData(undefined, colors, PLOTLY_UTC_1H)).toEqual([]);
    });
  });

  describe('createBollingerBandsData', () => {
    it('creates Bollinger Bands traces', () => {
      const bbData: BBData = [
        { timestamp: '2026-01-01T00:00:00Z', upper: 115, middle: 105, lower: 95 },
        { timestamp: '2026-01-01T01:00:00Z', upper: 120, middle: 110, lower: 100 },
      ];
      const colors = getThemeColors(true);
      const traces = createBollingerBandsData(bbData, colors, PLOTLY_UTC_1H);

      expect(traces).toHaveLength(3);
      expect(traces[0]!['name']).toBe('BB Upper');
      expect(traces[1]!['name']).toBe('BB Middle');
      expect(traces[2]!['name']).toBe('BB Lower');
    });

    it('returns empty array for empty/undefined BB', () => {
      const colors = getThemeColors(true);

      expect(createBollingerBandsData([], colors, PLOTLY_UTC_1H)).toEqual([]);
      expect(createBollingerBandsData(undefined, colors, PLOTLY_UTC_1H)).toEqual([]);
    });
  });

  describe('formatBacktestPlotlyXAxisTitle', () => {
    it('labels UTC-only when preference is UTC or unset', () => {
      expect(formatBacktestPlotlyXAxisTitle(undefined)).toBe('Time (UTC)');
      expect(formatBacktestPlotlyXAxisTitle('UTC')).toBe('Time (UTC)');
      expect(formatBacktestPlotlyXAxisTitle('  ')).toBe('Time (UTC)');
    });

    it('mentions LWC chart IANA while keeping UTC SoT on x', () => {
      expect(formatBacktestPlotlyXAxisTitle('Europe/Bucharest')).toBe(
        'Time (UTC) · LWC chart: Europe/Bucharest'
      );
    });
  });

  describe('createChartLayout', () => {
    it('creates chart layout with theme colors', () => {
      const colors = getThemeColors(true);
      const layout = createChartLayout({
        symbol: 'BTC/USDT',
        timeframe: '1h',
        showEquityCurve: false,
        hasRSI: false,
        hasMACD: false,
        colors,
      });

      expect(layout['paper_bgcolor']).toBe(colors.paper);
      expect(layout['plot_bgcolor']).toBe(colors.plot);
      expect(plotlyDeep(layout, 'title', 'text')).toBe('BTC/USDT 1h - Backtest Results');
      expect(plotlyDeep(layout, 'xaxis', 'utc')).toBe(true);
      expect(plotlyDeep(layout, 'xaxis', 'title', 'text')).toBe('Time (UTC)');
    });

    it('xaxis title references chart IANA when chartDisplayTimezone is not UTC', () => {
      const colors = getThemeColors(true);
      const layout = createChartLayout({
        symbol: 'BTC/USDT',
        timeframe: '1h',
        showEquityCurve: false,
        hasRSI: false,
        hasMACD: false,
        colors,
        chartDisplayTimezone: 'America/New_York',
      });

      expect(plotlyDeep(layout, 'xaxis', 'title', 'text')).toBe(
        'Time (UTC) · LWC chart: America/New_York'
      );
      expect(plotlyDeep(layout, 'xaxis', 'utc')).toBe(true);
    });

    it('adds yaxis2 when showEquityCurve is true', () => {
      const colors = getThemeColors(true);
      const layout = createChartLayout({
        symbol: 'BTC/USDT',
        timeframe: '1h',
        showEquityCurve: true,
        hasRSI: false,
        hasMACD: false,
        colors,
      });

      expect(layout['yaxis2']).toBeDefined();
      expect(plotlyDeep(layout, 'yaxis2', 'title')).toBe('Equity ($)');
    });

    it('adds yaxis3 when hasRSI is true', () => {
      const colors = getThemeColors(true);
      const layout = createChartLayout({
        symbol: 'BTC/USDT',
        timeframe: '1h',
        showEquityCurve: false,
        hasRSI: true,
        hasMACD: false,
        colors,
      });

      expect(layout['yaxis3']).toBeDefined();
      expect(plotlyDeep(layout, 'yaxis3', 'title')).toBe('RSI');
    });

    it('adds yaxis4 when hasMACD is true', () => {
      const colors = getThemeColors(true);
      const layout = createChartLayout({
        symbol: 'BTC/USDT',
        timeframe: '1h',
        showEquityCurve: false,
        hasRSI: false,
        hasMACD: true,
        colors,
      });

      expect(layout['yaxis4']).toBeDefined();
      expect(plotlyDeep(layout, 'yaxis4', 'title')).toBe('MACD');
    });
  });

  describe('createPlotlyChartConfig', () => {
    it('returns chart config with symbol/timeframe in filename', () => {
      const config = createPlotlyChartConfig('BTC/USDT', '1h');

      expect(config['displayModeBar']).toBe(true);
      expect(config['responsive']).toBe(true);
      expect(plotlyDeep(config, 'toImageButtonOptions', 'filename')).toBe('backtest_BTC_USDT_1h');
    });
  });
});
