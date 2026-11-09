// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { TRADING_ENDPOINT } from '@/config/api';
import {
  buildTradingAutomationByIdUrl,
  buildTradingAutomationPromoteFromBacktestUrl,
  buildTradingAutomationPromoteFromPublicBacktestUrl,
  buildTradingAutomationSelectAsActiveUrl,
  buildTradingAutomationsActiveUrl,
  buildTradingAutomationsEligibilityUrl,
  buildTradingAutomationsListUrl,
} from '@/config/tradingAutomationsUrls';

describe('tradingAutomationsUrls', () => {
  it('builds list, eligibility, active, by-id, select-as-active, and promote URLs under TRADING_ENDPOINT (SoT)', () => {
    expect(buildTradingAutomationsListUrl(50, 0)).toBe(
      `${TRADING_ENDPOINT}/automations?limit=50&offset=0`
    );
    expect(buildTradingAutomationsEligibilityUrl()).toBe(
      `${TRADING_ENDPOINT}/automations/eligibility`
    );
    expect(buildTradingAutomationsActiveUrl()).toBe(`${TRADING_ENDPOINT}/automations/active`);
    expect(buildTradingAutomationByIdUrl('a1')).toBe(`${TRADING_ENDPOINT}/automations/a1`);
    expect(buildTradingAutomationSelectAsActiveUrl('a1')).toBe(
      `${TRADING_ENDPOINT}/automations/a1/select-as-active`
    );
    expect(buildTradingAutomationPromoteFromBacktestUrl()).toBe(
      `${TRADING_ENDPOINT}/automations/promote-from-backtest`
    );
    expect(buildTradingAutomationPromoteFromPublicBacktestUrl()).toBe(
      `${TRADING_ENDPOINT}/automations/promote-from-public-backtest`
    );
  });

  it('encodes automation ids for path segments', () => {
    expect(buildTradingAutomationByIdUrl('x/y')).toBe(`${TRADING_ENDPOINT}/automations/x%2Fy`);
    expect(buildTradingAutomationSelectAsActiveUrl('x/y')).toBe(
      `${TRADING_ENDPOINT}/automations/x%2Fy/select-as-active`
    );
  });
});
