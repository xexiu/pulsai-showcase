// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { buildLiquidationHeatmapRequestUrl } from '@/lib/chart/build-liquidation-heatmap-request-url';
import { normalizeLiquidationHeatmapResponse } from '@/lib/chart/normalize-liquidation-heatmap-response';
import type {
  LiquidationHeatmapResponse,
  RawLiquidationHeatmapResponse,
} from '@/types/chart-liquidation-heatmap';
import { selectLiquidationHeatmapBandsForDraw } from '@/utils/chart-liquidation-heatmap-bands';
import { resolveLiquidationHeatmapBandAlpha } from '@/utils/chart-liquidation-heatmap-draw-metrics';
import {
  LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES,
  LIQUIDATION_HEATMAP_SIDE_RGB_CHANNELS,
} from '@/utils/constants/chartLiquidationHeatmap';

describe('liquidation heatmap band fillStyle (precomputed draw-spec, SoT channels)', () => {
  const snapshot: LiquidationHeatmapResponse = {
    provider: 'oi_leverage_estimate',
    quality: 'estimated',
    asOfMs: 1,
    symbol: 'BTCUSDT',
    ccxtSymbol: 'BTC/USDT',
    exchange: 'Binance',
    rangeLabel: '24h',
    bands: [
      { price: 90_000, intensityUsd: 1_000_000, side: 'long', leverageTier: 10 },
      { price: 95_000, intensityUsd: 5_000_000, side: 'short', leverageTier: 50 },
    ],
    warnings: [],
    cacheHit: false,
    historicalSnapshot: false,
    requestedAsOfMs: null,
  };

  it('locks the RGB channels SoT (Tailwind up/down family)', () => {
    expect(LIQUIDATION_HEATMAP_SIDE_RGB_CHANNELS).toEqual({
      long: '239, 68, 68',
      short: '34, 197, 94',
      unknown: '148, 163, 184',
    });
  });

  it('precomputes fillStyle from SoT channels + intensity-derived alpha (no per-frame regex)', () => {
    const specs = selectLiquidationHeatmapBandsForDraw(snapshot, {
      ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES,
      show: true,
    });

    expect(specs).toHaveLength(2);

    for (const spec of specs) {
      const expectedAlpha = resolveLiquidationHeatmapBandAlpha(spec.normalizedIntensity);

      expect(spec.fillStyle).toBe(
        `rgba(${LIQUIDATION_HEATMAP_SIDE_RGB_CHANNELS[spec.side]}, ${expectedAlpha})`
      );
    }
  });

  it('memoizes by (snapshot, preferences) ref so revision + apply share one compute', () => {
    const preferences = { ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES, show: true };

    const first = selectLiquidationHeatmapBandsForDraw(snapshot, preferences);
    const second = selectLiquidationHeatmapBandsForDraw(snapshot, preferences);

    // Same refs in → identical array out (no second O(n) pipeline pass).
    expect(second).toBe(first);

    // Different snapshot ref → fresh compute.
    const other = selectLiquidationHeatmapBandsForDraw({ ...snapshot }, preferences);

    expect(other).not.toBe(first);
  });
});

describe('buildLiquidationHeatmapRequestUrl', () => {
  it('builds query with defaults', () => {
    const url = buildLiquidationHeatmapRequestUrl({ symbol: 'BTC/USDT' });

    expect(url).toContain('/api/v1/market/liquidation-heatmap?');
    expect(url).toContain('symbol=BTC%2FUSDT');
    expect(url).toContain('exchange=Binance');
    expect(url).toContain('range=24h');
    expect(url).not.toContain('as_of_ms');
  });

  it('includes as_of_ms for historical backtest replay', () => {
    const url = buildLiquidationHeatmapRequestUrl({
      symbol: 'BTC/USDT',
      asOfMs: 1_700_000_000_000,
    });

    expect(url).toContain('as_of_ms=1700000000000');
  });
});

describe('normalizeLiquidationHeatmapResponse', () => {
  it('maps snake_case wire to camelCase view model', () => {
    const raw: RawLiquidationHeatmapResponse = {
      provider: 'oi_leverage_estimate',
      quality: 'estimated',
      as_of_ms: 1,
      symbol: 'BTCUSDT',
      ccxt_symbol: 'BTC/USDT',
      exchange: 'Binance',
      range_label: '24h',
      bands: [{ price: 90_000, intensity_usd: 1_000_000, side: 'long', leverage_tier: 10 }],
      warnings: ['estimated'],
      cache_hit: false,
    };

    const view = normalizeLiquidationHeatmapResponse(raw);

    expect(view.asOfMs).toBe(1);
    expect(view.bands[0]?.intensityUsd).toBe(1_000_000);
    expect(view.bands[0]?.side).toBe('long');
    expect(view.historicalSnapshot).toBe(false);
    expect(view.requestedAsOfMs).toBeNull();
  });

  it('maps unknown band sides to unknown', () => {
    const raw: RawLiquidationHeatmapResponse = {
      provider: 'oi_leverage_estimate',
      quality: 'estimated',
      as_of_ms: 1,
      symbol: 'BTCUSDT',
      ccxt_symbol: 'BTC/USDT',
      exchange: 'Binance',
      range_label: '24h',
      bands: [{ price: 1, intensity_usd: 1, side: 'weird', leverage_tier: null }],
      warnings: [],
      cache_hit: false,
    };

    const view = normalizeLiquidationHeatmapResponse(raw);

    expect(view.bands[0]?.side).toBe('unknown');
  });
});

describe('selectLiquidationHeatmapBandsForDraw', () => {
  it('returns empty when overlay hidden', () => {
    const bands = selectLiquidationHeatmapBandsForDraw(
      {
        provider: 'oi_leverage_estimate',
        quality: 'estimated',
        asOfMs: 1,
        symbol: 'BTCUSDT',
        ccxtSymbol: 'BTC/USDT',
        exchange: 'Binance',
        rangeLabel: '24h',
        bands: [{ price: 1, intensityUsd: 100, side: 'long', leverageTier: 10 }],
        warnings: [],
        cacheHit: false,
        historicalSnapshot: false,
        requestedAsOfMs: null,
      },
      { ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES, show: false }
    );

    expect(bands).toEqual([]);
  });

  it('filters by min intensity and sqrt-normalizes varying USD', () => {
    const bands = selectLiquidationHeatmapBandsForDraw(
      {
        provider: 'coinglass_model3',
        quality: 'vendor',
        asOfMs: 1,
        symbol: 'BTCUSDT',
        ccxtSymbol: 'BTC/USDT',
        exchange: 'Binance',
        rangeLabel: '24h',
        bands: [
          { price: 100, intensityUsd: 50, side: 'long', leverageTier: null },
          { price: 200, intensityUsd: 200, side: 'short', leverageTier: null },
        ],
        warnings: [],
        cacheHit: false,
        historicalSnapshot: false,
        requestedAsOfMs: null,
      },
      {
        ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES,
        show: true,
        minIntensityUsd: 40,
      }
    );

    expect(bands).toHaveLength(2);
    expect(bands.find((band) => band.price === 100)?.normalizedIntensity).toBeCloseTo(0.5);
    expect(bands.find((band) => band.price === 200)?.normalizedIntensity).toBe(1);
  });

  it('differentiates estimated bands by leverage tier when USD is uniform', () => {
    const bands = selectLiquidationHeatmapBandsForDraw(
      {
        provider: 'oi_leverage_estimate',
        quality: 'estimated',
        asOfMs: 1,
        symbol: 'BTCUSDT',
        ccxtSymbol: 'BTC/USDT',
        exchange: 'Binance',
        rangeLabel: '24h',
        bands: [
          { price: 90_000, intensityUsd: 2_000_000, side: 'long', leverageTier: 5 },
          { price: 88_000, intensityUsd: 2_000_000, side: 'long', leverageTier: 100 },
        ],
        warnings: ['estimated'],
        cacheHit: false,
        historicalSnapshot: false,
        requestedAsOfMs: null,
      },
      { ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES, show: true }
    );

    expect(bands).toHaveLength(2);
    expect(bands.find((band) => band.leverageTier === 5)?.normalizedIntensity).toBe(0);
    expect(bands.find((band) => band.leverageTier === 100)?.normalizedIntensity).toBe(1);
  });

  it('filters bands by leverage tier', () => {
    const bands = selectLiquidationHeatmapBandsForDraw(
      {
        provider: 'oi_leverage_estimate',
        quality: 'estimated',
        asOfMs: 1,
        symbol: 'BTCUSDT',
        ccxtSymbol: 'BTC/USDT',
        exchange: 'Binance',
        rangeLabel: '24h',
        bands: [
          { price: 100, intensityUsd: 200, side: 'long', leverageTier: 10 },
          { price: 200, intensityUsd: 200, side: 'short', leverageTier: 100 },
        ],
        warnings: [],
        cacheHit: false,
        historicalSnapshot: false,
        requestedAsOfMs: null,
      },
      {
        ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES,
        show: true,
        leverageTiers: [10],
      }
    );

    expect(bands).toHaveLength(1);
    expect(bands[0]?.leverageTier).toBe(10);
  });

  it('returns zero normalized intensity when all intensities are non-positive', () => {
    const bands = selectLiquidationHeatmapBandsForDraw(
      {
        provider: 'oi_leverage_estimate',
        quality: 'estimated',
        asOfMs: 1,
        symbol: 'BTCUSDT',
        ccxtSymbol: 'BTC/USDT',
        exchange: 'Binance',
        rangeLabel: '24h',
        bands: [{ price: 100, intensityUsd: 0, side: 'long', leverageTier: 10 }],
        warnings: [],
        cacheHit: false,
        historicalSnapshot: false,
        requestedAsOfMs: null,
      },
      { ...LIQUIDATION_HEATMAP_DEFAULT_PREFERENCES, show: true, minIntensityUsd: 0 }
    );

    expect(bands[0]?.normalizedIntensity).toBe(0);
  });
});
