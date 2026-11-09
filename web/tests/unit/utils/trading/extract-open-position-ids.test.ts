// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { extractOpenPaperPositionIdsFromPortfolio } from '@/utils/trading/extract-open-position-ids';

describe('extractOpenPaperPositionIdsFromPortfolio', () => {
  it('returns empty set for demo portfolio', () => {
    expect(
      extractOpenPaperPositionIdsFromPortfolio({ balance_usd: '1', btc_balance: '0' })
    ).toEqual(new Set());
  });

  it('collects position_id from paper open_positions', () => {
    const ids = extractOpenPaperPositionIdsFromPortfolio({
      mode: 'paper',
      exchange_connection_id: 'conn-1',
      balance: {},
      open_positions: [
        {
          position_id: 'p1',
          symbol: 'BTC/USDT:USDT',
          side: 'buy',
          market_type: 'swap',
          fill_count: 1,
          compound_cap: 0,
          compound_remaining: 0,
        },
        {
          position_id: 'p2',
          symbol: 'ETH/USDT',
          side: 'buy',
          market_type: 'spot',
          fill_count: 2,
          compound_cap: 3,
          compound_remaining: 1,
        },
      ],
    });

    expect(ids).toEqual(new Set(['p1', 'p2']));
  });

  it('ignores blank position_id strings', () => {
    const ids = extractOpenPaperPositionIdsFromPortfolio({
      mode: 'paper',
      exchange_connection_id: 'c',
      balance: {},
      open_positions: [
        {
          position_id: '  ',
          symbol: 'BTC/USDT',
          side: 'buy',
          market_type: 'spot',
          fill_count: 0,
          compound_cap: 0,
          compound_remaining: 0,
        },
        {
          position_id: 'valid',
          symbol: 'BTC/USDT',
          side: 'buy',
          market_type: 'spot',
          fill_count: 0,
          compound_cap: 0,
          compound_remaining: 0,
        },
      ],
    });

    expect(ids).toEqual(new Set(['valid']));
  });
});
