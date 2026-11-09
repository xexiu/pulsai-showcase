/**
 * Pure helper functions for useTradePageModel.
 * Extracted to reduce cyclomatic complexity of the main hook.
 */

import { DEFAULT_SYMBOL, type TradingSymbol } from '@pulsai/shared';

import type { FeaturesConfig, FeaturesConfigFuturesTradingUiKey } from '@/types/app-config';
import type { MarketType, TradingMode } from '@/types/tradingBarrel';
import { isStaffRole } from '@/utils/constants/core';
import {
  MARKET_TYPE,
  TRADING_DEFAULT_DEMO_MODE,
  TRADING_MODE,
  TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED,
} from '@/utils/constants/trading';

type UserLike = { role?: string; subscription_tier?: string } | null | undefined;

export type FuturesFeatureConfigLike =
  | {
      features?: Partial<Pick<FeaturesConfig, FeaturesConfigFuturesTradingUiKey>>;
    }
  | null
  | undefined;

export function resolveActiveMode(
  selectedMode: TradingMode | null,
  modes: TradingMode[],
  user: UserLike
): TradingMode | null {
  if (selectedMode) return selectedMode;
  if (modes[0]) return modes[0];
  if (user != null) return TRADING_DEFAULT_DEMO_MODE;

  return null;
}

export function deriveOrderSymbol(
  activeMode: TradingMode | null,
  preferredSymbol: TradingSymbol
): TradingSymbol {
  if (activeMode == null) return DEFAULT_SYMBOL;
  if (activeMode.kind === TRADING_MODE.DEMO) return DEFAULT_SYMBOL;

  return preferredSymbol;
}

export function checkIsAdmin(user: UserLike): boolean {
  if (!user) return false;

  return isStaffRole(user.role);
}

/**
 * Show Spot/Futures segmented control on **paper or live** CCXT modes (never demo) when the
 * exchange supports swap. Admins see it without the global `futures_paper_trading` flag.
 * Non-admins need the flag. Reads ``TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED`` on each mode row
 * from GET /trading/modes (exchange capability).
 */
export function checkFuturesMarketTypeUiVisible(
  isCcxtPaperOrLive: boolean,
  isDemo: boolean,
  exchangeSupportsFuturesSwap: boolean,
  featureFuturesPaperTrading: boolean,
  isAdmin: boolean
): boolean {
  if (isDemo || !isCcxtPaperOrLive) return false;
  if (!exchangeSupportsFuturesSwap) return false;
  if (isAdmin) return true;

  return featureFuturesPaperTrading;
}

/** Who may select swap (admin/super_admin). Subscription tiers may be added later (e.g. elite). */
export function checkFuturesSelectionAllowed(isAdmin: boolean): boolean {
  return isAdmin;
}

export function buildFuturesQueryEnabled(
  futuresMarketUiVisible: boolean,
  futuresSelectionAllowed: boolean,
  marketType: MarketType,
  connectionId: string | null | undefined
): boolean {
  return (
    futuresMarketUiVisible &&
    futuresSelectionAllowed &&
    marketType === MARKET_TYPE.SWAP &&
    Boolean(connectionId)
  );
}

export function resolveFuturesParam<T>(marketType: MarketType, value: T): T | undefined {
  if (marketType !== MARKET_TYPE.SWAP) return undefined;

  return value;
}

/** True when paper **or live** mode lists swap support on the active connection (modes payload). */
export function resolveExchangeSupportsFuturesOnMode(
  activeMode: TradingMode | null,
  modes: TradingMode[]
): boolean {
  if (activeMode?.kind !== TRADING_MODE.PAPER && activeMode?.kind !== TRADING_MODE.LIVE)
    return false;
  const modeFromList = modes.find((m) => m.id === activeMode.id);

  return Boolean(
    modeFromList?.[TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED] ??
    activeMode?.[TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED]
  );
}
