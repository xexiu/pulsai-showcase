// @vitest-environment node
/**
 * plotly-chart-helpers tests — candlestick + theme + markers (split for §7.2 line cap).
 *
 * @see plotly-chart-helpers.prediction-signal-compound.test.ts
 * @see docs/04-structural/CODING_STANDARDS.md
 */

import { describe, expect, it } from 'vitest';

import {
  createCandlestickData,
  getThemeColors,
  type CandleData,
} from '@/utils/plotly-chart-helpers';
import { yForEntrySignalMarker } from '@/utils/plotly-chart-helpers/entry-signal-marker-y';

import { mockCandles, plotlyDeep, PLOTLY_UTC_1H, px } from './plotly-chart-helpers.test-harness';

describe('plotly-chart-helpers', () => {
  describe('yForEntrySignalMarker', () => {
    it('places BUY below candle low and SELL above candle high', () => {
      const c: CandleData = {
        timestamp: '2026-01-01T00:00:00Z',
        open: 100,
        high: 110,
        low: 95,
        close: 105,
      };

      expect(yForEntrySignalMarker(c, true)).toBeLessThan(c.low);
      expect(yForEntrySignalMarker(c, false)).toBeGreaterThan(c.high);
    });
  });

  describe('getThemeColors', () => {
    it('returns dark theme colors for isDark=true', () => {
      const colors = getThemeColors(true);

      expect(colors.paper).toBe('#1f2937');
      expect(colors.plot).toBe('#111827');
      expect(colors.text).toBe('#e5e7eb');
      expect(colors.bullish).toBe('#26a69a');
      expect(colors.bearish).toBe('#ef5350');
      expect(colors.equityCurveLine).toBe('hsl(271 91% 65%)');
    });

    it('returns light theme colors for isDark=false', () => {
      const colors = getThemeColors(false);

      expect(colors.paper).toBe('#ffffff');
      expect(colors.plot).toBe('#f9fafb');
      expect(colors.text).toBe('#111827');
      expect(colors.equityCurveLine).toBe('hsl(271 91% 55%)');
    });
  });

  describe('createCandlestickData', () => {
    it('creates candlestick trace data', () => {
      const colors = getThemeColors(true);
      const trace = createCandlestickData(mockCandles, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(trace!.type).toBe('candlestick');
      expect(trace!['x']).toEqual([px('2026-01-01T00:00:00Z'), px('2026-01-01T01:00:00Z')]);
      expect(trace!['open']).toEqual([100, 105]);
      expect(trace!['high']).toEqual([110, 115]);
      expect(trace!['low']).toEqual([95, 100]);
      expect(trace!['close']).toEqual([105, 110]);
      expect(plotlyDeep(trace, 'increasing', 'line', 'color')).toBe(colors.bullish);
      expect(plotlyDeep(trace, 'decreasing', 'line', 'color')).toBe(colors.bearish);
      expect(trace!['hoverinfo']).toBe('text');
      expect(Array.isArray(trace!['hovertext'])).toBe(true);
      const ht0 = (trace!['hovertext'] as string[])[0];

      expect(ht0).toContain('Bar open:');
      expect(ht0).toContain('Bar close:');
    });

    it('omits model feature dump even when model_features present', () => {
      const colors = getThemeColors(true);
      const withFeatures: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          model_features: { rsi_14: 42.5, macd: 0.00012 },
        },
      ];
      const trace = createCandlestickData(withFeatures, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).toContain('Bar open:');
      expect(ht[0]).toContain('Bar close:');
      expect(ht[0]).not.toContain('Model inputs');
      expect(ht[0]).not.toContain('macd');
      expect(ht[0]).not.toContain('rsi_14');
    });

    it('with chartMlModelHover, shows OHLC only when model_features absent', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          model_features: null,
        },
      ];
      const trace = createCandlestickData(candles, colors, PLOTLY_UTC_1H, {
        chartMlModelHover: true,
      });

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).toContain('Bar open:');
      expect(ht[0]).toContain('Bar close:');
      expect(ht[0]).toContain('Open:');
      expect(ht[0]).not.toContain('Model inputs');
      expect(ht[0]).not.toContain('<b>Momentum');
    });

    it('with chartMlModelHover, shows prediction/confidence and omits model features', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          ml_prediction: 'HOLD',
          ml_confidence_percent: 42.25,
          model_features: { rsi_14: 42.5, macd: 0.12 },
        },
      ];
      const trace = createCandlestickData(candles, colors, PLOTLY_UTC_1H, {
        chartMlModelHover: true,
      });

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).toContain('Bar open:');
      expect(ht[0]).toContain('Bar close:');
      expect(ht[0]).toContain('HOLD');
      expect(ht[0]).toContain('42.3%');
      expect(ht[0]).not.toContain('Model inputs');
      expect(ht[0]).not.toContain('Model features');
      expect(ht[0]).not.toContain('<b>Momentum');
      expect(ht[0]).not.toContain('rsi_14');
      expect(ht[0]).not.toContain('macd');
    });

    it('with chartMlModelHover, shows prediction inline without "Model prediction" header', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          model_features: null,
          ml_prediction: 'HOLD',
          ml_confidence_percent: 42.25,
        },
      ];
      const trace = createCandlestickData(candles, colors, PLOTLY_UTC_1H, {
        chartMlModelHover: true,
      });

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).toContain('Bar open:');
      expect(ht[0]).toContain('Bar close:');
      expect(ht[0]).toContain('HOLD');
      expect(ht[0]).toContain('42.3%');
      expect(ht[0]).not.toContain('Model prediction');
    });

    it('without chartMlModelHover, omits Model inputs when model_features missing', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
        },
      ];
      const trace = createCandlestickData(candles, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).toContain('Bar open:');
      expect(ht[0]).toContain('Bar close:');
      expect(ht[0]).not.toContain('Model inputs');
    });

    it('does not append P0 parity block when indicator_groups.p0_exact is present (classic hover)', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          indicator_groups: { p0_exact: { rsi_14: 44.2 } },
        },
      ];
      const trace = createCandlestickData(candles, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).not.toContain('P0 indicators (parity)');
      expect(ht[0]).not.toContain('rsi_14');
    });

    it('does not append P0 parity or model features when chartMlModelHover', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          ml_prediction: 'HOLD',
          ml_confidence_percent: 40,
          model_features: { rsi_14: 50 },
          indicator_groups: { p0_exact: { macd_hist: 0.01 } },
        },
      ];
      const trace = createCandlestickData(candles, colors, PLOTLY_UTC_1H, {
        chartMlModelHover: true,
      });

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      const hover0 = ht[0];

      expect(hover0).toBeDefined();
      expect(hover0).toContain('HOLD');
      expect(hover0).not.toContain('<b>Momentum');
      expect(hover0).not.toContain('rsi_14');
      expect(hover0).not.toContain('P0 indicators (parity)');
      expect(hover0).not.toContain('macd_hist');
    });

    it('does not append P1 alias parity block when indicator_groups.p1_alias is present', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          indicator_groups: { p1_alias: { support_pa_20: 95.5 } },
        },
      ];
      const trace = createCandlestickData(candles, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).not.toContain('P1 aliases (parity)');
      expect(ht[0]).not.toContain('support_pa_20');
    });

    it('does not append P4 chart-pattern parity block when indicator_groups.p4_chart_pattern is present', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
          indicator_groups: { p4_chart_pattern: { cp_support_line: 98.2 } },
        },
      ];
      const trace = createCandlestickData(candles, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).not.toContain('P4 chart-pattern (parity)');
      expect(ht[0]).not.toContain('cp_support_line');
    });

    it('omits Bar close when timeframe is unknown', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          open: 100,
          high: 110,
          low: 95,
          close: 105,
        },
      ];
      const trace = createCandlestickData(candles, colors, {
        chartTimezone: 'UTC',
        timeframe: 'invalid',
      });

      expect(trace).not.toBeNull();
      const ht = trace!['hovertext'] as string[];

      expect(ht[0]).toContain('Bar open:');
      expect(ht[0]).not.toContain('Bar close:');
    });

    it('returns null for empty candles array', () => {
      const colors = getThemeColors(true);
      const trace = createCandlestickData([], colors, PLOTLY_UTC_1H);

      expect(trace).toBeNull();
    });

    it('sorts candles by timestamp (fixes overlapping chart visual)', () => {
      const colors = getThemeColors(true);
      const unsorted: CandleData[] = [
        { timestamp: '2026-02-06T12:00:00Z', open: 100, high: 110, low: 95, close: 105 },
        { timestamp: '2026-02-04T00:00:00Z', open: 100, high: 110, low: 95, close: 105 },
        { timestamp: '2026-02-05T08:00:00Z', open: 100, high: 110, low: 95, close: 105 },
      ];
      const trace = createCandlestickData(unsorted, colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(trace!['x']).toEqual([
        px('2026-02-04T00:00:00Z'),
        px('2026-02-05T08:00:00Z'),
        px('2026-02-06T12:00:00Z'),
      ]);
    });
  });
});
