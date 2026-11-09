// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  formatDemoPnlPlaceholderUsd,
  getDemoTradingFeePercentLabel,
} from '@/utils/trading/demo-display';

describe('getDemoTradingFeePercentLabel', () => {
  it('returns percent string aligned with TRADING_DEMO_FEE_RATE_FRACTION', () => {
    expect(getDemoTradingFeePercentLabel()).toBe('0.10%');
  });
});

describe('formatDemoPnlPlaceholderUsd', () => {
  it('returns signed zero P&L placeholder', () => {
    expect(formatDemoPnlPlaceholderUsd()).toBe('+$0.00');
  });
});
