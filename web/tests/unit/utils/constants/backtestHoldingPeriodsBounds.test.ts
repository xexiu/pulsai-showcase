// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  BACKTEST_HOLDING_PERIODS_MAX_HTF,
  resolveBacktestHoldingPeriodsMax,
} from '@/utils/constants/backtestHoldingPeriodsBounds';

describe('resolveBacktestHoldingPeriodsMax', () => {
  it('returns 1000 for 5m and 15m (ceiling binds)', () => {
    expect(resolveBacktestHoldingPeriodsMax('5m')).toBe(1000);
    expect(resolveBacktestHoldingPeriodsMax('15m')).toBe(1000);
  });

  it('returns 672 for 30m (14 days × 48 candles/day)', () => {
    expect(resolveBacktestHoldingPeriodsMax('30m')).toBe(672);
  });

  it('returns HTF cap for 1h and unknown timeframes', () => {
    expect(resolveBacktestHoldingPeriodsMax('1h')).toBe(BACKTEST_HOLDING_PERIODS_MAX_HTF);
    expect(resolveBacktestHoldingPeriodsMax('2h')).toBe(BACKTEST_HOLDING_PERIODS_MAX_HTF);
  });
});
