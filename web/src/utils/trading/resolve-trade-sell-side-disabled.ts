/**
 * Whether the order panel should disable the **sell** side for demo/paper modes.
 *
 * - **Spot:** selling requires free base (close / reduce long). Uses portfolio balances.
 * - **Perpetual (swap):** sell opens a short; margin is enforced at placement, not here.
 */

import type { MarketType } from '@/types/tradingDomain';
import { MARKET_TYPE, TRADING_MODE } from '@/utils/constants/trading';
import { hasSellableBasePosition } from '@/utils/trading/preset-capital-usd';

export function resolveTradeSellSideDisabled(params: {
  isAuthenticated: boolean;
  portfolio: Record<string, unknown> | undefined;
  portfolioLoading: boolean;
  portfolioError: boolean;
  modeStr: string;
  marketType: MarketType;
  baseAsset: string;
}): boolean {
  const portfolioReady =
    params.isAuthenticated &&
    params.portfolio !== undefined &&
    !params.portfolioLoading &&
    !params.portfolioError;

  if (!portfolioReady) {
    return false;
  }

  if (params.modeStr !== TRADING_MODE.DEMO && params.modeStr !== TRADING_MODE.PAPER) {
    return false;
  }

  if (params.marketType === MARKET_TYPE.SWAP) {
    return false;
  }

  return !hasSellableBasePosition(params.modeStr, params.portfolio, params.baseAsset);
}
