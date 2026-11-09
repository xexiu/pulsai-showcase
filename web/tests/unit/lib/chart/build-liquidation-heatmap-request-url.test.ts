// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { buildLiquidationHeatmapRequestUrl } from '@/lib/chart/build-liquidation-heatmap-request-url';

describe('buildLiquidationHeatmapRequestUrl', () => {
  it('includes viewport sync query params', () => {
    const url = buildLiquidationHeatmapRequestUrl({
      symbol: 'BTC/USDT',
      range: '24h',
      timeframe: '5m',
      visibleCandleCount: 120,
    });

    expect(url).toContain('symbol=BTC%2FUSDT');
    expect(url).toContain('range=24h');
    expect(url).toContain('timeframe=5m');
    expect(url).toContain('visible_candle_count=120');
  });
});
