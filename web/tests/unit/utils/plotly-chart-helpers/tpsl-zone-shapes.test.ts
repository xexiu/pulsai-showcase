// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  createTpSlZoneShapes,
  type PlotlyShape,
} from '@/utils/plotly-chart-helpers/tpsl-zone-shapes';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

function makeSignal(overrides: Partial<SignalData>): SignalData {
  return {
    timestamp: '2026-01-01T00:00:00Z',
    type: 'BUY',
    price: 100,
    ...overrides,
  };
}

const PLOTLY_UTC_5M: PlotlyTimeOptions = { chartTimezone: 'UTC', timeframe: '5m' };

describe('createTpSlZoneShapes', () => {
  it('returns empty array when no signals have TP/SL', () => {
    const signals: SignalData[] = [
      makeSignal({ type: 'BUY', timestamp: '2026-01-01T00:00:00Z' }),
      makeSignal({ type: 'EXIT', timestamp: '2026-01-02T00:00:00Z' }),
    ];

    expect(createTpSlZoneShapes(signals, PLOTLY_UTC_5M)).toEqual([]);
  });

  it('accepts stop_loss/take_profit aliases when *_price fields are absent', () => {
    const signals: SignalData[] = [
      makeSignal({
        type: 'BUY',
        timestamp: '2026-01-01T00:00:00Z',
        price: 100,
        stop_loss: 98,
        take_profit: 104,
        side: 'long',
      }),
      makeSignal({
        type: 'EXIT',
        timestamp: '2026-01-03T00:00:00Z',
        price: 104,
        side: 'long',
      }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M);

    expect(shapes.length).toBe(2);
    expect(typeof shapes[0]?.x0).toBe('number');
  });

  it('creates green TP zone and red SL zone for long trade', () => {
    const signals: SignalData[] = [
      makeSignal({
        type: 'BUY',
        timestamp: '2026-01-01T00:00:00Z',
        price: 100,
        stop_loss_price: 98,
        take_profit_price: 104,
        side: 'long',
      }),
      makeSignal({
        type: 'EXIT',
        timestamp: '2026-01-03T00:00:00Z',
        price: 104,
        side: 'long',
      }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M);

    expect(shapes.length).toBe(2);

    const tpShape = shapes.find((s: PlotlyShape) => s.fillcolor === 'rgba(144,238,144,0.20)');
    const slShape = shapes.find((s: PlotlyShape) => s.fillcolor === 'rgba(255, 82, 82, 0.18)');

    expect(tpShape).toBeDefined();
    expect(slShape).toBeDefined();

    expect(tpShape?.y0).toBe(100);
    expect(tpShape?.y1).toBe(104);
    expect(slShape?.y0).toBe(98);
    expect(slShape?.y1).toBe(100);
  });

  it('creates mirrored zones for short trade', () => {
    const signals: SignalData[] = [
      makeSignal({
        type: 'SELL',
        timestamp: '2026-01-01T00:00:00Z',
        price: 100,
        stop_loss_price: 102,
        take_profit_price: 96,
        side: 'short',
      }),
      makeSignal({
        type: 'EXIT',
        timestamp: '2026-01-03T00:00:00Z',
        price: 96,
        side: 'short',
      }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M);

    expect(shapes.length).toBe(2);

    const tpShape = shapes.find((s: PlotlyShape) => s.fillcolor === 'rgba(144,238,144,0.20)');
    const slShape = shapes.find((s: PlotlyShape) => s.fillcolor === 'rgba(255, 82, 82, 0.18)');

    expect(tpShape).toBeDefined();
    expect(slShape).toBeDefined();
  });

  it('creates min, 1R, and full TP bands when levels are present', () => {
    const signals: SignalData[] = [
      makeSignal({
        type: 'BUY',
        timestamp: '2026-01-01T00:00:00Z',
        price: 100,
        stop_loss_price: 95,
        min_tp_price: 106,
        tp_1r_price: 105,
        full_tp_price: 108,
        side: 'long',
      }),
      makeSignal({
        type: 'EXIT',
        timestamp: '2026-01-03T00:00:00Z',
        price: 108,
        side: 'long',
      }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M);

    expect(shapes).toHaveLength(4);
    expect(shapes[0]?.fillcolor).toBe('rgba(255, 82, 82, 0.18)');
    expect(shapes[1]?.fillcolor).toBe('rgba(144,238,144,0.20)');
    expect(shapes[2]?.fillcolor).toBe('rgba(168,255,172,0.20)');
    expect(shapes[3]?.fillcolor).toBe('rgba(0,100,0,0.15)');
  });

  it('only creates TP zone when SL is undefined (trailing stop)', () => {
    const signals: SignalData[] = [
      makeSignal({
        type: 'BUY',
        timestamp: '2026-01-01T00:00:00Z',
        price: 100,
        take_profit_price: 104,
        side: 'long',
      }),
      makeSignal({
        type: 'EXIT',
        timestamp: '2026-01-03T00:00:00Z',
        side: 'long',
      }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M);

    expect(shapes.length).toBe(1);
    expect(shapes[0]?.fillcolor).toBe('rgba(144,238,144,0.20)');
  });

  it('only creates SL zone when TP is undefined', () => {
    const signals: SignalData[] = [
      makeSignal({
        type: 'BUY',
        timestamp: '2026-01-01T00:00:00Z',
        price: 100,
        stop_loss_price: 98,
        side: 'long',
      }),
      makeSignal({
        type: 'EXIT',
        timestamp: '2026-01-03T00:00:00Z',
        side: 'long',
      }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M);

    expect(shapes.length).toBe(1);
    expect(shapes[0]?.fillcolor).toBe('rgba(255, 82, 82, 0.18)');
  });

  it('uses last candle timestamp when no paired EXIT found', () => {
    const signals: SignalData[] = [
      makeSignal({
        type: 'BUY',
        timestamp: '2026-01-01T00:00:00Z',
        price: 100,
        stop_loss_price: 98,
        take_profit_price: 104,
        side: 'long',
      }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M, '2026-01-05T00:00:00Z');

    expect(shapes.length).toBe(2);
    expect(typeof shapes[0]?.x1).toBe('number');
  });

  it('handles multiple trades with correct pairing', () => {
    const signals: SignalData[] = [
      makeSignal({
        type: 'BUY',
        timestamp: '2026-01-01T00:00:00Z',
        price: 100,
        stop_loss_price: 98,
        take_profit_price: 104,
        side: 'long',
      }),
      makeSignal({ type: 'EXIT', timestamp: '2026-01-02T00:00:00Z', side: 'long' }),
      makeSignal({
        type: 'SELL',
        timestamp: '2026-01-03T00:00:00Z',
        price: 105,
        stop_loss_price: 107,
        take_profit_price: 101,
        side: 'short',
      }),
      makeSignal({ type: 'EXIT', timestamp: '2026-01-04T00:00:00Z', side: 'short' }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M);

    expect(shapes.length).toBe(4);
  });

  it('skips EXIT signals without entry pairing', () => {
    const signals: SignalData[] = [
      makeSignal({ type: 'EXIT', timestamp: '2026-01-01T00:00:00Z', side: 'long' }),
    ];

    const shapes = createTpSlZoneShapes(signals, PLOTLY_UTC_5M);

    expect(shapes.length).toBe(0);
  });
});
