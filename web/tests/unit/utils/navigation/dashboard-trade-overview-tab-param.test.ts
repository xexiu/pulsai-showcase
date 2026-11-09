// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  effectiveTradeOverviewTabFromSearchParam,
  parseTradeOverviewTabSearchParam,
} from '@/utils/trading/parse-trade-overview-tab-search-param';

describe('parseTradeOverviewTabSearchParam', () => {
  it('returns null for null or empty', () => {
    expect(parseTradeOverviewTabSearchParam(null)).toBeNull();
    expect(parseTradeOverviewTabSearchParam('')).toBeNull();
  });

  it('accepts orders, history, stats', () => {
    expect(parseTradeOverviewTabSearchParam('orders')).toBe('orders');
    expect(parseTradeOverviewTabSearchParam('history')).toBe('history');
    expect(parseTradeOverviewTabSearchParam('stats')).toBe('stats');
  });

  it('rejects unknown keys', () => {
    expect(parseTradeOverviewTabSearchParam('chart')).toBeNull();
    expect(parseTradeOverviewTabSearchParam('nope')).toBeNull();
  });
});

describe('effectiveTradeOverviewTabFromSearchParam', () => {
  it('defaults invalid or missing to orders', () => {
    expect(effectiveTradeOverviewTabFromSearchParam(null)).toBe('orders');
    expect(effectiveTradeOverviewTabFromSearchParam('bad')).toBe('orders');
  });

  it('passes through valid keys', () => {
    expect(effectiveTradeOverviewTabFromSearchParam('stats')).toBe('stats');
    expect(effectiveTradeOverviewTabFromSearchParam('history')).toBe('history');
  });
});
