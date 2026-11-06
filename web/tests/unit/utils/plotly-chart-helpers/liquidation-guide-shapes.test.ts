// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { BACKTEST_EXIT_TYPE } from '@/utils/constants/backtestExitTypes';
import { createLiquidationGuideShapes } from '@/utils/plotly-chart-helpers/liquidation-guide-shapes';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';

const plotlyTime = { chartTimezone: 'UTC', timeframe: '4h' } as const;

describe('createLiquidationGuideShapes', () => {
  const signals: SignalData[] = [
    {
      timestamp: '2026-01-01T00:00:00Z',
      type: 'BUY',
      price: 100,
      side: 'long',
    },
    {
      timestamp: '2026-01-02T00:00:00Z',
      type: 'EXIT',
      price: 90.3096,
      side: 'long',
      reason: BACKTEST_EXIT_TYPE.LIQUIDATION,
      theoretical_liquidation_price: 90.4,
    },
  ];

  it('returns empty when disabled', () => {
    expect(createLiquidationGuideShapes(signals, false, plotlyTime)).toEqual([]);
  });

  it('draws theoretical liq line and slippage gap when enabled', () => {
    const shapes = createLiquidationGuideShapes(signals, true, plotlyTime);

    expect(shapes).toHaveLength(2);
    expect(shapes[0]?.type).toBe('line');
    expect(shapes[0]?.y0).toBe(90.4);
    expect(shapes[1]?.y0).toBe(90.4);
    expect(shapes[1]?.y1).toBe(90.3096);
  });

  it('ignores non-liquidation exits', () => {
    const nonLiq: SignalData[] = [
      { timestamp: '2026-01-01T00:00:00Z', type: 'BUY', price: 100, side: 'long' },
      {
        timestamp: '2026-01-02T00:00:00Z',
        type: 'EXIT',
        price: 95,
        side: 'long',
        reason: 'stop_loss',
      },
    ];

    expect(createLiquidationGuideShapes(nonLiq, true, plotlyTime)).toEqual([]);
  });
});
