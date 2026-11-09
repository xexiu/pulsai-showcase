// @vitest-environment node
import { describe, expect, it } from 'vitest';

import {
  TRADING_CHART_OVERVIEW_TAB_KEY,
  TRADING_OVERVIEW_TAB_DEFAULT_KEY,
  TRADING_OVERVIEW_TAB_KEYS,
  type PaperTradingOverviewTabKey,
} from '@/utils/constants/trading';
import { resolveTradeActiveOverviewTab } from '@/utils/trading/resolve-trade-active-overview-tab';

describe('resolveTradeActiveOverviewTab', () => {
  const withoutChart = [...TRADING_OVERVIEW_TAB_KEYS] as PaperTradingOverviewTabKey[];
  const withChart = [...withoutChart, TRADING_CHART_OVERVIEW_TAB_KEY];

  it('returns selected tab when it is in the allowed set', () => {
    expect(resolveTradeActiveOverviewTab(withoutChart, 'history')).toBe('history');
    expect(resolveTradeActiveOverviewTab(withChart, 'chart')).toBe('chart');
  });

  it('falls back to default when selected tab is not allowed (e.g. chart is not an overview tab)', () => {
    expect(resolveTradeActiveOverviewTab(withoutChart, TRADING_CHART_OVERVIEW_TAB_KEY)).toBe(
      TRADING_OVERVIEW_TAB_DEFAULT_KEY
    );
  });

  it('falls back when allowed set is empty', () => {
    expect(resolveTradeActiveOverviewTab([], 'history')).toBe(TRADING_OVERVIEW_TAB_DEFAULT_KEY);
  });
});
