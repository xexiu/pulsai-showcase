// @vitest-environment node
import { describe, expect, it } from 'vitest';

import type { TradingMode } from '@/types/tradingBarrel';
import { TRADING_MODE } from '@/utils/constants/trading';
import { findDemoMode, findFirstPaperMode } from '@/utils/trading/select-trading-mode-from-list';

const demo: TradingMode = {
  id: 'demo',
  label: 'Demo',
  label_key: 'dashboard.trade.modeSwitcher.demo',
  label_params: {},
  kind: TRADING_MODE.DEMO,
  exchange_connection_id: null,
  fallback_simulated: false,
};

const paperA: TradingMode = {
  id: 'paper:a',
  label: 'Paper a',
  label_key: 'dashboard.trade.modeSwitcher.paper',
  label_params: { exchange: 'a' },
  kind: TRADING_MODE.PAPER,
  exchange_connection_id: 'c1',
  fallback_simulated: false,
};

const paperB: TradingMode = {
  id: 'paper:b',
  label: 'Paper b',
  label_key: 'dashboard.trade.modeSwitcher.paper',
  label_params: { exchange: 'b' },
  kind: TRADING_MODE.PAPER,
  exchange_connection_id: 'c2',
  fallback_simulated: false,
};

describe('select-trading-mode-from-list', () => {
  it('findDemoMode returns the demo entry', () => {
    expect(findDemoMode([paperA, demo])).toEqual(demo);
  });

  it('findFirstPaperMode returns the first paper entry in list order', () => {
    expect(findFirstPaperMode([demo, paperB, paperA])).toEqual(paperB);
  });

  it('returns undefined when no match', () => {
    expect(findDemoMode([paperA])).toBeUndefined();
    expect(findFirstPaperMode([demo])).toBeUndefined();
  });
});
