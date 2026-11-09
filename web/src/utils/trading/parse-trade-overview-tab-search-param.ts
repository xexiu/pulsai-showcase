import {
  TRADING_OVERVIEW_TAB_DEFAULT_KEY,
  type PaperTradingOverviewTabKey,
  resolveTradeOverviewTabKeys,
} from '@/utils/constants/trading';

const ALLOWED = new Set(resolveTradeOverviewTabKeys());

/**
 * Validates `overviewTab` search param for `/dashboard/trade`.
 */
export function parseTradeOverviewTabSearchParam(
  raw: string | null | undefined
): PaperTradingOverviewTabKey | null {
  if (raw == null || raw === '') {
    return null;
  }

  if (!ALLOWED.has(raw as PaperTradingOverviewTabKey)) {
    return null;
  }

  return raw as PaperTradingOverviewTabKey;
}

export function effectiveTradeOverviewTabFromSearchParam(
  raw: string | null | undefined
): PaperTradingOverviewTabKey {
  return parseTradeOverviewTabSearchParam(raw) ?? TRADING_OVERVIEW_TAB_DEFAULT_KEY;
}
