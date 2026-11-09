// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { classicIndicatorConfigToOptions } from '@/utils/indicators/classic-indicator-config-from-api';

describe('classicIndicatorConfigToOptions', () => {
  it('maps BE snake_case periods into useIndicators options', () => {
    expect(
      classicIndicatorConfigToOptions({
        timeframe: '15m',
        rsi_period: 9,
        macd_fast: 12,
        macd_slow: 26,
        macd_signal: 9,
        bb_period: 15,
        bb_std: 2,
        divergence_lookback: 10,
      })
    ).toEqual({
      rsiPeriod: 9,
      macdFastPeriod: 12,
      macdSlowPeriod: 26,
      macdSignalPeriod: 9,
      bbPeriod: 15,
      bbStdDev: 2,
    });
  });

  it('returns empty object when config is undefined', () => {
    expect(classicIndicatorConfigToOptions(undefined)).toEqual({});
  });
});
