/**
 * Pure bracket eligibility for POST /trading/orders (paper + demo + live).
 *
 * Cross-ref BE: `apps/api/src/application/services/unified_trading/order_preflight.py`
 * (`validate_order_bracket_contract`).
 */

import {
  MARKET_TYPE,
  ORDER_SIDE,
  SPOT_PLAN_BRACKET_SUPPORTED_EXCHANGE_IDS,
  TRADING_MODE,
} from '@/utils/constants/trading';

export function shouldAttachBracketPrices(
  modeStr: string,
  side: string,
  marketType?: string
): boolean {
  if (modeStr === TRADING_MODE.DEMO && side === ORDER_SIDE.BUY) {
    return true;
  }

  const isCcxtExecution = modeStr === TRADING_MODE.PAPER || modeStr === TRADING_MODE.LIVE;

  if (isCcxtExecution && side === ORDER_SIDE.BUY) return true;
  if (isCcxtExecution && side === ORDER_SIDE.SELL && marketType === MARKET_TYPE.SWAP) return true;

  return false;
}

/** True when paper/live spot plan brackets are implemented for this venue (BE registry). */
export function isSpotPlanBracketVenueSupported(exchangeId: string | null | undefined): boolean {
  if (exchangeId == null || exchangeId === '') return false;
  const key = exchangeId.trim().toLowerCase();

  return (SPOT_PLAN_BRACKET_SUPPORTED_EXCHANGE_IDS as readonly string[]).includes(key);
}

/**
 * When false, omit SL/TP from the JSON for paper/live spot buys (unsupported venue).
 * If ``venueExchangeId`` is omitted, returns true so the API remains authoritative.
 */
export function shouldSendSpotBracketPrices(
  modeStr: string,
  side: string,
  marketType: string | undefined,
  venueExchangeId: string | null | undefined
): boolean {
  if (!shouldAttachBracketPrices(modeStr, side, marketType)) {
    return false;
  }
  const mt = marketType ?? MARKET_TYPE.SPOT;
  const isCcxt = modeStr === TRADING_MODE.PAPER || modeStr === TRADING_MODE.LIVE;

  if (isCcxt && mt === MARKET_TYPE.SPOT && side === ORDER_SIDE.BUY) {
    if (venueExchangeId == null || venueExchangeId === '') {
      return true;
    }

    return isSpotPlanBracketVenueSupported(venueExchangeId);
  }

  return true;
}
