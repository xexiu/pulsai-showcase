/**
 * Infer **effective** market type for activity UI when API rows disagree with CCXT symbols.
 *
 * CCXT unified swap symbols include a settle suffix (`BTC/USDT:USDT`). If `market_type` is
 * missing or incorrectly `spot`, side labels must still use perp Long/Short semantics.
 *
 * For **order rows**, use {@link resolveEffectiveMarketTypeForOrderDisplay}: plain `BASE/QUOTE`
 * pairs never surface futures Long/Short labels even when `market_type` was saved wrong.
 */

import type { MarketType } from '@/types/tradingBarrel';
import { MARKET_TYPE } from '@/utils/constants/trading';

/** True when ``symbol`` looks like a CCXT linear/inverse perp unified id (contains `:`). */
export function isCcxtUnifiedSwapStyleSymbol(symbol: string): boolean {
  return symbol.trim().includes(':');
}

/**
 * Prefer persisted ``market_type``; override to swap when the symbol clearly denotes a perp
 * but the row says spot / is absent (stale API / import bugs).
 */
export function resolveEffectiveMarketTypeForActivitySide(
  symbol: string,
  marketType: MarketType | null | undefined
): MarketType | undefined {
  if (isCcxtUnifiedSwapStyleSymbol(symbol)) {
    if (marketType === MARKET_TYPE.SPOT || marketType == null || marketType === undefined) {
      return MARKET_TYPE.SWAP;
    }
  }

  return marketType ?? undefined;
}

/**
 * Órdenes / fills **display** SoT: reconcile persisted ``market_type`` with the symbol string.
 *
 * - **Trust ``market_type=swap``** first: some venue/import paths persist ``BTC/USDT`` without a
 *   CCXT settle suffix; chart overlays and SL/TP still require perp semantics.
 * - Otherwise symbols **without** `:` stay **spot** (plain ``BASE/QUOTE`` pairs).
 * - Unified perp ids (**with** `:`) use {@link resolveEffectiveMarketTypeForActivitySide} (e.g.
 *   upgrade spot → swap when the symbol clearly denotes a perp).
 */
export function resolveEffectiveMarketTypeForOrderDisplay(
  symbol: string,
  marketType: MarketType | null | undefined
): MarketType | undefined {
  if (marketType === MARKET_TYPE.SWAP) {
    return MARKET_TYPE.SWAP;
  }
  if (!isCcxtUnifiedSwapStyleSymbol(symbol)) {
    return MARKET_TYPE.SPOT;
  }

  return resolveEffectiveMarketTypeForActivitySide(symbol, marketType);
}

/** Whether swap-specific venue columns (lev, mark, uPnL, avg entry from venue) apply. */
export function isEffectiveSwapMarket(
  symbol: string,
  marketType: MarketType | null | undefined
): boolean {
  return resolveEffectiveMarketTypeForOrderDisplay(symbol, marketType) === MARKET_TYPE.SWAP;
}
