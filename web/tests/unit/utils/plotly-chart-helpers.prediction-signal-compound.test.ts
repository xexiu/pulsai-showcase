// @vitest-environment node
/**
 * plotly-chart-helpers tests — prediction dots, entry/exit signals, DCA compound traces.
 *
 * @see plotly-chart-helpers.test.ts (candlestick block)
 */

import { describe, expect, it } from 'vitest';

import {
  createCompoundFillData,
  createPredictionData,
  createSignalData,
  getThemeColors,
  type CandleData,
  type SignalData,
} from '@/utils/plotly-chart-helpers';
import {
  BACKTEST_SIGNAL_MARKER_EXECUTION_NOTE,
  PREDICTION_MARKER_SIZE,
  PREDICTION_OPACITY_ACTIONABLE,
} from '@/utils/plotly-chart-helpers/constants';
import { confidenceToPlotlyEntryMarkerSize } from '@/utils/signal-marker-confidence-visual';

import { mockSignals, plotlyDeep, PLOTLY_UTC_1H, px } from './plotly-chart-helpers.test-harness';

describe('plotly-chart-helpers — predictions & signals', () => {
  describe('createPredictionData', () => {
    it('exposes prediction type and confidence in hover text', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        { timestamp: '2026-01-01T00:00:00Z', open: 100, high: 110, low: 95, close: 105 },
      ];
      const trace = createPredictionData({
        predictions: [{ timestamp: '2026-01-01T00:00:00Z', type: 'BUY', confidence: 55.2 }],
        type: 'BUY',
        candles,
        colors,
        plotlyTime: PLOTLY_UTC_1H,
      });

      expect(trace).not.toBeNull();
      expect(trace!['hovertemplate']).toBe('%{text}<extra></extra>');
      const text = trace!['text'] as string[];

      expect(text[0]).toContain('BUY');
      expect(text[0]).toContain('55.2');
    });

    it('with chartMlModelHover, shows prediction and confidence (no model-feature dump)', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        { timestamp: '2026-01-01T00:00:00Z', open: 100, high: 110, low: 95, close: 105 },
      ];
      const trace = createPredictionData({
        predictions: [{ timestamp: '2026-01-01T00:00:00Z', type: 'BUY', confidence: 55.2 }],
        type: 'BUY',
        candles,
        colors,
        plotlyTime: PLOTLY_UTC_1H,
        chartMlModelHover: true,
      });

      expect(trace).not.toBeNull();
      const text = trace!['text'] as string[];

      expect(text[0]).toContain('Prediction: BUY');
      expect(text[0]).toContain('55.2');
      expect(text[0]).not.toContain('model inputs');
      expect(text[0]).not.toContain('Price trace');
    });

    it('anchors BUY prediction dots below candle low and SELL dots above candle high', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        { timestamp: '2026-01-01T00:00:00Z', open: 100, high: 110, low: 95, close: 105 },
      ];
      const buyTrace = createPredictionData({
        predictions: [{ timestamp: '2026-01-01T00:00:00Z', type: 'BUY', confidence: 55.2 }],
        type: 'BUY',
        candles,
        colors,
        plotlyTime: PLOTLY_UTC_1H,
      });
      const sellTrace = createPredictionData({
        predictions: [{ timestamp: '2026-01-01T00:00:00Z', type: 'SELL', confidence: 72.4 }],
        type: 'SELL',
        candles,
        colors,
        plotlyTime: PLOTLY_UTC_1H,
      });

      expect(buyTrace).not.toBeNull();
      expect(sellTrace).not.toBeNull();
      expect((buyTrace!['y'] as number[])[0]).toBeLessThan(candles[0]!.low);
      expect((sellTrace!['y'] as number[])[0]).toBeGreaterThan(candles[0]!.high);
    });

    it('uses stronger prediction marker visibility for BUY/SELL dots', () => {
      const colors = getThemeColors(true);
      const candles: CandleData[] = [
        { timestamp: '2026-01-01T00:00:00Z', open: 100, high: 110, low: 95, close: 105 },
      ];
      const trace = createPredictionData({
        predictions: [{ timestamp: '2026-01-01T00:00:00Z', type: 'BUY', confidence: 85 }],
        type: 'BUY',
        candles,
        colors,
        plotlyTime: PLOTLY_UTC_1H,
      });

      expect(trace).not.toBeNull();
      expect(plotlyDeep(trace, 'marker', 'size')).toBe(PREDICTION_MARKER_SIZE);
      expect(plotlyDeep(trace, 'marker', 'opacity')).toBe(PREDICTION_OPACITY_ACTIONABLE);
    });
  });

  describe('createSignalData', () => {
    it('creates BUY signal markers', () => {
      const colors = getThemeColors(true);
      const trace = createSignalData(mockSignals, 'BUY', colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(trace!.type).toBe('scatter');
      expect(trace!['mode']).toBe('markers');
      expect(plotlyDeep(trace, 'marker', 'symbol')).toBe('triangle-up');
      expect(plotlyDeep(trace, 'marker', 'color')).toBe(colors.bullish);
      expect(trace!['x']).toEqual([px('2026-01-01T00:00:00Z')]);
    });

    it('maps entry marker size from confidence (low smaller, high larger)', () => {
      const colors = getThemeColors(true);
      const signals: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'BUY', price: 100, confidence: 20 },
        { timestamp: '2026-01-01T02:00:00Z', type: 'BUY', price: 102, confidence: 90 },
      ];
      const trace = createSignalData(signals, 'BUY', colors, PLOTLY_UTC_1H);
      const sizes = plotlyDeep(trace, 'marker', 'size') as number[];

      expect(sizes[0]).toBe(confidenceToPlotlyEntryMarkerSize(20));
      expect(sizes[1]).toBe(confidenceToPlotlyEntryMarkerSize(90));
      expect(sizes[0]).toBeLessThan(sizes[1]!);
    });

    it('creates SELL signal markers', () => {
      const colors = getThemeColors(true);
      const trace = createSignalData(mockSignals, 'SELL', colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(plotlyDeep(trace, 'marker', 'symbol')).toBe('triangle-down');
      expect(plotlyDeep(trace, 'marker', 'color')).toBe(colors.bearish);
    });

    it('returns null when no matching signals', () => {
      const colors = getThemeColors(true);
      const buyOnlySignals: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'BUY', price: 100 },
      ];
      const trace = createSignalData(buyOnlySignals, 'SELL', colors, PLOTLY_UTC_1H);

      expect(trace).toBeNull();
    });

    it('excludes compound_fill reason from primary BUY trace (DCA uses separate trace)', () => {
      const colors = getThemeColors(true);
      const signals: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'BUY', price: 100, confidence: 80 },
        {
          timestamp: '2026-01-01T02:00:00Z',
          type: 'BUY',
          price: 95,
          confidence: 80,
          reason: 'compound_fill',
        },
      ];
      const trace = createSignalData(signals, 'BUY', colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      expect(trace!['x']).toEqual([px('2026-01-01T00:00:00Z')]);
      expect(trace!['y']).toEqual([100]);
    });

    it('hover includes entry_fee when present (Chart DRY plan)', () => {
      const colors = getThemeColors(true);
      const signals: SignalData[] = [
        {
          timestamp: '2026-01-01T00:00:00Z',
          type: 'BUY',
          price: 50000,
          confidence: 72.5,
          entry_fee: 1.25,
        },
      ];
      const trace = createSignalData(signals, 'BUY', colors, PLOTLY_UTC_1H);

      expect(trace).not.toBeNull();
      const hover0 = (plotlyDeep(trace, 'text') as string[])[0];

      expect(hover0).toContain('BUY @ $50,000.00');
      expect(hover0).toContain(BACKTEST_SIGNAL_MARKER_EXECUTION_NOTE);
      expect(hover0).toContain('Confidence: 72.5%');
      expect(hover0).toContain('Entry Fee: $1.25');
    });

    it('with chartMlModelHover, signal hover never dumps model features', () => {
      const colors = getThemeColors(true);
      const ts = '2026-01-01T00:00:00Z';
      const signals: SignalData[] = [
        { timestamp: ts, type: 'BUY', price: 50000, confidence: 72.5 },
      ];
      const candleMap = new Map<string, CandleData>([
        [
          ts,
          { timestamp: ts, open: 1, high: 2, low: 0.5, close: 1.5, model_features: { rsi_14: 50 } },
        ],
      ]);
      const withFeatures = createSignalData(signals, 'BUY', colors, PLOTLY_UTC_1H, {
        candlesByTimestamp: candleMap,
        chartMlModelHover: true,
      });
      const withoutFeaturesOnCandle = createSignalData(signals, 'BUY', colors, PLOTLY_UTC_1H, {
        candlesByTimestamp: new Map([
          [ts, { timestamp: ts, open: 1, high: 2, low: 0.5, close: 1.5, model_features: null }],
        ]),
        chartMlModelHover: true,
      });

      expect(withFeatures).not.toBeNull();
      expect(withoutFeaturesOnCandle).not.toBeNull();
      for (const trace of [withFeatures, withoutFeaturesOnCandle]) {
        const hover0 = (plotlyDeep(trace, 'text') as string[])[0];

        expect(hover0).toContain('BUY @ $50,000.00');
        expect(hover0).toContain('Confidence: 72.5%');
        expect(hover0).not.toContain('<b>Momentum');
        expect(hover0).not.toContain('Model features');
        expect(hover0).not.toContain('rsi_14');
      }
    });

    it('with candlesByTimestamp, BUY y is below candle low (triangle under bar)', () => {
      const colors = getThemeColors(true);
      const ts = '2026-01-01T00:00:00Z';
      const candle: CandleData = {
        timestamp: ts,
        open: 100,
        high: 110,
        low: 95,
        close: 105,
      };
      const trace = createSignalData(
        [{ timestamp: ts, type: 'BUY', price: 100, confidence: 80 }],
        'BUY',
        colors,
        PLOTLY_UTC_1H,
        { candlesByTimestamp: new Map([[ts, candle]]) }
      );

      expect(trace).not.toBeNull();
      expect((trace!['y'] as number[])[0]).toBeLessThan(candle.low);
    });

    it('with candlesByTimestamp, SELL y is above candle high (triangle over bar)', () => {
      const colors = getThemeColors(true);
      const ts = '2026-01-01T00:00:00Z';
      const candle: CandleData = {
        timestamp: ts,
        open: 100,
        high: 110,
        low: 95,
        close: 105,
      };
      const trace = createSignalData(
        [{ timestamp: ts, type: 'SELL', price: 100, confidence: 80 }],
        'SELL',
        colors,
        PLOTLY_UTC_1H,
        { candlesByTimestamp: new Map([[ts, candle]]) }
      );

      expect(trace).not.toBeNull();
      expect((trace!['y'] as number[])[0]).toBeGreaterThan(candle.high);
    });
  });

  describe('createCompoundFillData', () => {
    it('creates markers only for compound_fill entries of the given side', () => {
      const colors = getThemeColors(true);
      const signals: SignalData[] = [
        { timestamp: '2026-01-01T00:00:00Z', type: 'BUY', price: 100 },
        {
          timestamp: '2026-01-01T02:00:00Z',
          type: 'BUY',
          price: 95,
          reason: 'compound_fill',
        },
        {
          timestamp: '2026-01-01T03:00:00Z',
          type: 'SELL',
          price: 90,
          reason: 'compound_fill',
        },
      ];
      const longDca = createCompoundFillData(signals, colors, 'BUY', PLOTLY_UTC_1H);
      const shortDca = createCompoundFillData(signals, colors, 'SELL', PLOTLY_UTC_1H);

      expect(longDca).not.toBeNull();
      expect(longDca!['x']).toEqual([px('2026-01-01T02:00:00Z')]);
      expect(longDca!['y']).toEqual([95]);
      expect(longDca!['name']).toBe('DCA fill');

      expect(shortDca).not.toBeNull();
      expect(shortDca!['x']).toEqual([px('2026-01-01T03:00:00Z')]);
      expect(shortDca!['name']).toBe('DCA fill (short)');
    });

    it('uses injected localized hover labels for DCA traces', () => {
      const colors = getThemeColors(true);
      const signals: SignalData[] = [
        {
          timestamp: '2026-01-01T02:00:00Z',
          type: 'BUY',
          price: 95,
          reason: 'compound_fill',
          confidence: 88.4,
        },
      ];
      const trace = createCompoundFillData(signals, colors, 'BUY', PLOTLY_UTC_1H, {
        dcaFill: 'Relleno DCA',
        long: 'Largo',
        short: 'Corto',
        confidence: 'Confianza:',
        entryFee: 'Comisión de entrada:',
        exitReason: 'Motivo:',
        exitNetPnl: 'PnL neto:',
        exitFee: 'Comisión de salida:',
        stopLoss: 'Stop Loss:',
        takeProfit: 'Take Profit:',
      });

      expect(trace).not.toBeNull();
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Relleno DCA (Largo)');
      expect((plotlyDeep(trace, 'text') as string[])[0]).toContain('Confianza: 88.4%');
    });
  });
});
