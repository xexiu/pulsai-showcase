// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { demoPortfolioBracketSlTpForOrders } from '@/utils/trading/demo-portfolio-bracket-for-orders';

describe('demoPortfolioBracketSlTpForOrders', () => {
  it('returns null pair when not a demo snapshot', () => {
    expect(demoPortfolioBracketSlTpForOrders({ mode: 'paper' })).toEqual({ sl: null, tp: null });
  });

  it('returns bracket strings from demo snapshot', () => {
    expect(
      demoPortfolioBracketSlTpForOrders({
        balance_usd: '1',
        btc_balance: '0.1',
        bracket_stop_loss_usd: '50000',
        bracket_take_profit_usd: '60000',
      })
    ).toEqual({ sl: '50000', tp: '60000' });
  });
});
