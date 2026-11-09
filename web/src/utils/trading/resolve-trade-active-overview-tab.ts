/**
 * Resolves which overview tab is active when the allowed tab set can change (e.g. chart feature flag).
 */

import {
  TRADING_OVERVIEW_TAB_DEFAULT_KEY,
  type PaperTradingOverviewTabKey,
} from '@/utils/constants/trading';

export function resolveTradeActiveOverviewTab(
  overviewTabKeys: readonly PaperTradingOverviewTabKey[],
  selectedTab: PaperTradingOverviewTabKey
): PaperTradingOverviewTabKey {
  if (overviewTabKeys.includes(selectedTab)) {
    return selectedTab;
  }

  return TRADING_OVERVIEW_TAB_DEFAULT_KEY;
}
