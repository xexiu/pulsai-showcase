// @vitest-environment node
import { describe, expect, it } from 'vitest';

import type { TradingMode } from '@/types/tradingDomain';
import { TRADING_MODE_LABEL_PARAM_EXCHANGE } from '@/utils/constants/trading';
import { resolveVenueExchangeIdFromTradingMode } from '@/utils/trading/resolve-venue-exchange-id-from-trading-mode';

function modeWithExchange(exchange: string): TradingMode {
  return {
    id: 'paper:c1',
    label: 'Paper',
    label_key: 'dashboard.trade.modeSwitcher.paper',
    label_params: { [TRADING_MODE_LABEL_PARAM_EXCHANGE]: exchange },
    kind: 'paper',
    exchange_connection_id: 'c1',
    fallback_simulated: false,
  };
}

describe('resolveVenueExchangeIdFromTradingMode', () => {
  it('returns undefined for null', () => {
    expect(resolveVenueExchangeIdFromTradingMode(null)).toBeUndefined();
  });

  it('returns undefined when label_params omits exchange', () => {
    const m: TradingMode = {
      ...modeWithExchange('bitget'),
      label_params: {},
    };

    expect(resolveVenueExchangeIdFromTradingMode(m)).toBeUndefined();
  });

  it('normalizes to lowercase trimmed id', () => {
    expect(resolveVenueExchangeIdFromTradingMode(modeWithExchange('  BitGet  '))).toBe('bitget');
  });
});
