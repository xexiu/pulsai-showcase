// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { collectBacktestEntryHeatmapRequests } from '@/lib/backtest/collect-backtest-entry-heatmap-requests';
import type { LiquidationHeatmapResponse } from '@/types/chart-liquidation-heatmap';
import { BACKTEST_LIQUIDATION_HEATMAP_MAX_ENTRY_REQUESTS } from '@/utils/constants/backtestLiquidationHeatmap';
import { createBacktestLiquidationHeatmapShapes } from '@/utils/plotly-chart-helpers/backtest-liquidation-heatmap-shapes';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';

const snapshot: LiquidationHeatmapResponse = {
  provider: 'oi_leverage_estimate',
  quality: 'estimated',
  asOfMs: 1_700_000_000_000,
  symbol: 'BTCUSDT',
  ccxtSymbol: 'BTC/USDT',
  exchange: 'Binance',
  rangeLabel: '24h',
  bands: [
    { price: 90_000, intensityUsd: 2_000_000, side: 'long', leverageTier: 10 },
    { price: 92_000, intensityUsd: 2_000_000, side: 'short', leverageTier: 50 },
  ],
  warnings: [],
  cacheHit: false,
  historicalSnapshot: true,
  requestedAsOfMs: 1_700_000_000_000,
};

describe('collectBacktestEntryHeatmapRequests', () => {
  it('dedupes entry timestamps and skips non-entry signals', () => {
    const signals: SignalData[] = [
      { type: 'BUY', timestamp: '2024-01-01T00:00:00.000Z', price: 1, side: 'long' },
      { type: 'EXIT', timestamp: '2024-01-02T00:00:00.000Z', price: 2, side: 'long' },
      { type: 'SELL', timestamp: '2024-01-01T00:00:00.000Z', price: 1, side: 'short' },
    ];

    const requests = collectBacktestEntryHeatmapRequests(signals);

    expect(requests).toHaveLength(1);
    expect(requests[0]?.entryKey).toBe('2024-01-01T00:00:00.000Z');
    expect(requests[0]?.asOfMs).toBe(Date.parse('2024-01-01T00:00:00.000Z'));
  });

  it('caps unique entry requests to guard against first-render thundering-herd', () => {
    const signals: SignalData[] = Array.from(
      { length: BACKTEST_LIQUIDATION_HEATMAP_MAX_ENTRY_REQUESTS + 25 },
      (_, index) => ({
        type: 'BUY' as const,
        timestamp: new Date(Date.UTC(2024, 0, 1, 0, index)).toISOString(),
        price: 1,
        side: 'long' as const,
      })
    );

    const requests = collectBacktestEntryHeatmapRequests(signals);

    expect(requests).toHaveLength(BACKTEST_LIQUIDATION_HEATMAP_MAX_ENTRY_REQUESTS);
  });

  it('prefers entries inside the visible candle window when capped', () => {
    const early: SignalData[] = Array.from({ length: 80 }, (_, index) => ({
      type: 'BUY' as const,
      timestamp: new Date(Date.UTC(2017, 0, 1 + index)).toISOString(),
      price: 1,
      side: 'long' as const,
    }));
    const visible: SignalData[] = [
      {
        type: 'BUY',
        timestamp: '2024-06-01T00:00:00.000Z',
        price: 1,
        side: 'long',
      },
      {
        type: 'BUY',
        timestamp: '2024-07-01T00:00:00.000Z',
        price: 1,
        side: 'long',
      },
    ];

    const requests = collectBacktestEntryHeatmapRequests([...early, ...visible], {
      windowStartMs: Date.parse('2024-01-01T00:00:00.000Z'),
      windowEndMs: Date.parse('2024-12-31T00:00:00.000Z'),
      maxRequests: 10,
    });

    expect(requests.map((r) => r.entryKey)).toEqual([
      '2024-06-01T00:00:00.000Z',
      '2024-07-01T00:00:00.000Z',
      ...early.slice(0, 8).map((s) => s.timestamp),
    ]);
  });
});

describe('createBacktestLiquidationHeatmapShapes', () => {
  const plotlyTime = { chartTimezone: 'UTC', timeframe: '4h' } as const;

  it('returns empty when disabled', () => {
    const shapes = createBacktestLiquidationHeatmapShapes(
      [],
      false,
      new Map([['2024-01-01T00:00:00.000Z', snapshot]]),
      plotlyTime
    );

    expect(shapes).toEqual([]);
  });

  it('draws horizontal bands across entry active window', () => {
    const entryTs = '2024-01-01T00:00:00.000Z';
    const exitTs = '2024-01-02T00:00:00.000Z';
    const signals: SignalData[] = [
      { type: 'BUY', timestamp: entryTs, price: 91_000, side: 'long' },
      { type: 'EXIT', timestamp: exitTs, price: 90_500, side: 'long' },
    ];

    const shapes = createBacktestLiquidationHeatmapShapes(
      signals,
      true,
      new Map([[entryTs, snapshot]]),
      plotlyTime
    );

    expect(shapes.length).toBeGreaterThan(0);
    expect(shapes.every((shape) => shape.type === 'line' && shape.layer === 'below')).toBe(true);
    const band = shapes.find((shape) => shape.y0 === 90_000);

    expect(band).toBeDefined();
    expect(typeof band?.x0).toBe('number');
    expect(typeof band?.x1).toBe('number');
    expect((band?.x0 as number) < (band?.x1 as number)).toBe(true);
  });
});
