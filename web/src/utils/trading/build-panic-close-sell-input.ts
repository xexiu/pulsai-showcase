/**
 * Market sell entire base balance at reference price (panic close / flatten spot long).
 */

import type { BuildPlaceOrderRequestInput, MarketType } from '@/types/tradingBarrel';
import {
  MARKET_TYPE,
  ORDER_SIDE,
  ORDER_TYPE,
  TRADING_MODE,
  type TradingModeKind,
} from '@/utils/constants/trading';

const ERR_NO_PRICE = 'Reference price unavailable. Wait for live price.';
const ERR_NO_BASE = 'No base balance to close.';

/** Market sell a specific base amount (spot long exit for one FIFO lot or panic = full balance). */
export function buildMarketSellPlaceOrderFromBtcAmount(args: {
  btcAmountStr: string;
  referencePriceUsd: number | null;
  orderSymbol: string;
  modeStr: TradingModeKind;
  connectionId: string | null | undefined;
  /** From the filled order row (or form defaults when row omits swap fields). */
  marketType?: MarketType | null;
  leverage?: number | null;
}): BuildPlaceOrderRequestInput {
  const ref = args.referencePriceUsd;

  if (ref == null || !Number.isFinite(ref) || ref <= 0) {
    throw new Error(ERR_NO_PRICE);
  }

  const btc = Number.parseFloat(args.btcAmountStr.trim());

  if (!Number.isFinite(btc) || btc <= 0) {
    throw new Error(ERR_NO_BASE);
  }

  const usd = btc * ref;

  const base: BuildPlaceOrderRequestInput = {
    orderType: ORDER_TYPE.MARKET,
    limitPrice: '',
    livePrice: ref,
    amountUsd: usd.toFixed(2),
    modeStr: args.modeStr,
    connectionId: args.connectionId ?? null,
    side: ORDER_SIDE.SELL,
    orderSymbol: args.orderSymbol,
    stopLoss: '',
    takeProfit: '',
    ...(args.modeStr === TRADING_MODE.DEMO
      ? { demoMarketSellAmountBtc: args.btcAmountStr.trim() }
      : {}),
  };

  const mt = args.marketType ?? null;
  const lev = args.leverage;

  if (mt === MARKET_TYPE.SWAP && lev != null && Number.isFinite(lev) && lev > 0) {
    base.marketType = MARKET_TYPE.SWAP;
    base.leverage = lev;
    if (args.modeStr === TRADING_MODE.PAPER || args.modeStr === TRADING_MODE.LIVE) {
      base.reduceOnly = true;
    }
  }

  return base;
}

export function buildPanicCloseSellPlaceOrderInput(args: {
  btcBalanceStr: string;
  referencePriceUsd: number | null;
  orderSymbol: string;
  modeStr: TradingModeKind;
  connectionId: string | null | undefined;
}): BuildPlaceOrderRequestInput {
  return buildMarketSellPlaceOrderFromBtcAmount({
    btcAmountStr: args.btcBalanceStr,
    referencePriceUsd: args.referencePriceUsd,
    orderSymbol: args.orderSymbol,
    modeStr: args.modeStr,
    connectionId: args.connectionId,
  });
}
