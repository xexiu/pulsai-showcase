import { DEFAULT_SYMBOL } from '@pulsai/shared';
import { describe, expect, it } from 'vitest';

import {
  buildFuturesQueryEnabled,
  checkFuturesMarketTypeUiVisible,
  checkFuturesSelectionAllowed,
  checkIsAdmin,
  deriveOrderSymbol,
  resolveActiveMode,
  resolveExchangeSupportsFuturesOnMode,
  resolveFuturesParam,
} from '@/hooks/useTradePageModel.helpers';
import type { TradingMode } from '@/types/tradingBarrel';
import {
  TRADING_DEFAULT_DEMO_MODE,
  TRADING_MODE,
  TRADING_MODE_LABEL_KEY,
  TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED,
} from '@/utils/constants/trading';

const demoMode: TradingMode = {
  id: 'demo-1',
  label: 'Demo',
  label_key: 'dashboard.trade.modeSwitcher.demo',
  label_params: {},
  kind: 'demo',
  exchange_connection_id: null,
  fallback_simulated: false,
};

const paperMode: TradingMode = {
  id: 'paper-1',
  label: 'Paper',
  label_key: 'dashboard.trade.modeSwitcher.paper',
  label_params: { exchange: 'bitget' },
  kind: 'paper',
  exchange_connection_id: 'conn-1',
  fallback_simulated: false,
  [TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED]: false,
};

describe('resolveActiveMode', () => {
  it('returns selectedMode when provided', () => {
    expect(resolveActiveMode(paperMode, [demoMode], {})).toBe(paperMode);
  });

  it('falls back to first mode when selectedMode is null', () => {
    expect(resolveActiveMode(null, [demoMode, paperMode], {})).toBe(demoMode);
  });

  it('falls back to default demo mode when modes are empty and user exists', () => {
    expect(resolveActiveMode(null, [], { role: 'user' })).toBe(TRADING_DEFAULT_DEMO_MODE);
  });

  it('returns null when no mode and no user', () => {
    expect(resolveActiveMode(null, [], null)).toBeNull();
  });
});

describe('deriveOrderSymbol', () => {
  it('returns DEFAULT_SYMBOL for demo mode', () => {
    expect(deriveOrderSymbol(demoMode, 'ETH/USDT')).toBe(DEFAULT_SYMBOL);
  });

  it('returns preferredSymbol for paper mode', () => {
    expect(deriveOrderSymbol(paperMode, 'ETH/USDT')).toBe('ETH/USDT');
  });

  it('returns DEFAULT_SYMBOL when activeMode is null', () => {
    expect(deriveOrderSymbol(null, 'ETH/USDT')).toBe(DEFAULT_SYMBOL);
  });
});

describe('checkIsAdmin', () => {
  it('returns true for admin', () => {
    expect(checkIsAdmin({ role: 'admin' })).toBe(true);
  });

  it('returns true for super_admin', () => {
    expect(checkIsAdmin({ role: 'super_admin' })).toBe(true);
  });

  it('returns false for regular user', () => {
    expect(checkIsAdmin({ role: 'user' })).toBe(false);
  });

  it('returns false for null user', () => {
    expect(checkIsAdmin(null)).toBe(false);
  });
});

describe('checkFuturesMarketTypeUiVisible', () => {
  it('returns true when CCXT paper/live, not demo, exchange supports swap, feature on, non-admin', () => {
    expect(checkFuturesMarketTypeUiVisible(true, false, true, true, false)).toBe(true);
  });

  it('returns true for admin when exchange supports futures even if feature flag off', () => {
    expect(checkFuturesMarketTypeUiVisible(true, false, true, false, true)).toBe(true);
  });

  it('returns false for non-admin when feature flag off', () => {
    expect(checkFuturesMarketTypeUiVisible(true, false, true, false, false)).toBe(false);
  });

  it('returns false for demo even when other flags true', () => {
    expect(checkFuturesMarketTypeUiVisible(true, true, true, true, true)).toBe(false);
  });

  it('returns false when not CCXT paper or live (e.g. would-be demo-only path)', () => {
    expect(checkFuturesMarketTypeUiVisible(false, false, true, true, false)).toBe(false);
  });

  it('returns false when exchange does not support futures paper', () => {
    expect(checkFuturesMarketTypeUiVisible(true, false, false, true, true)).toBe(false);
  });
});

describe('checkFuturesSelectionAllowed', () => {
  it('returns true for admin', () => {
    expect(checkFuturesSelectionAllowed(true)).toBe(true);
  });

  it('returns false for non-admin', () => {
    expect(checkFuturesSelectionAllowed(false)).toBe(false);
  });
});

describe('buildFuturesQueryEnabled', () => {
  it('returns true when UI visible, selection allowed, swap, connectionId present', () => {
    expect(buildFuturesQueryEnabled(true, true, 'swap', 'conn-1')).toBe(true);
  });

  it('returns false when market is spot', () => {
    expect(buildFuturesQueryEnabled(true, true, 'spot', 'conn-1')).toBe(false);
  });

  it('returns false when futures market UI not visible', () => {
    expect(buildFuturesQueryEnabled(false, true, 'swap', 'conn-1')).toBe(false);
  });

  it('returns false when futures selection not allowed', () => {
    expect(buildFuturesQueryEnabled(true, false, 'swap', 'conn-1')).toBe(false);
  });

  it('returns false when connectionId is null', () => {
    expect(buildFuturesQueryEnabled(true, true, 'swap', null)).toBe(false);
  });

  it('returns false when connectionId is undefined', () => {
    expect(buildFuturesQueryEnabled(true, true, 'swap', undefined)).toBe(false);
  });
});

describe('resolveFuturesParam', () => {
  it('returns the value when market is swap', () => {
    expect(resolveFuturesParam('swap', 5)).toBe(5);
  });

  it('returns undefined when market is spot', () => {
    expect(resolveFuturesParam('spot', 5)).toBeUndefined();
  });
});

describe('resolveExchangeSupportsFuturesOnMode', () => {
  const paperWithFutures: TradingMode = {
    ...paperMode,
    [TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED]: true,
  };

  const liveWithFutures: TradingMode = {
    id: 'live-1',
    label: 'Live',
    label_key: TRADING_MODE_LABEL_KEY.LIVE,
    label_params: { exchange: 'bitget' },
    kind: TRADING_MODE.LIVE,
    exchange_connection_id: 'conn-live',
    fallback_simulated: false,
    [TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED]: true,
  };

  it('returns false when active mode is demo', () => {
    expect(resolveExchangeSupportsFuturesOnMode(demoMode, [demoMode])).toBe(false);
  });

  it('returns true from activeMode when list has no matching id (paper)', () => {
    expect(resolveExchangeSupportsFuturesOnMode(paperWithFutures, [])).toBe(true);
  });

  it('returns true for live when futures_paper_supported on active mode', () => {
    expect(resolveExchangeSupportsFuturesOnMode(liveWithFutures, [])).toBe(true);
  });

  it('returns false for live when futures swap flag is false', () => {
    expect(
      resolveExchangeSupportsFuturesOnMode(
        { ...liveWithFutures, [TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED]: false },
        []
      )
    ).toBe(false);
  });

  it('prefers mode list entry over activeMode when both set', () => {
    const listEntry: TradingMode = {
      ...paperWithFutures,
      id: paperWithFutures.id,
      [TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED]: false,
    };

    expect(resolveExchangeSupportsFuturesOnMode(paperWithFutures, [listEntry])).toBe(false);
  });
});
