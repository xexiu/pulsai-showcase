/**
 * Paper trading hook return types (useTradePageModel / useTradeFormState / useTradeDemoActivityQueries).
 *
 * SoT: extracted from `trading-barrel.ts` in Phase 2.7.27 (≤400 LOC SRP).
 * Consumers import from `@/types/tradingBarrel` which re-exports.
 */

import type { OrderSizeInputSemantic, SLTPMode, TradingModeKind } from '@/types/trading-wire';
import type {
  LeverageTiersResponse,
  MarketType,
  OrderSide,
  OrderType,
  TradingMode,
} from '@/types/tradingDomain';
import type {
  PlaceOrderResponse,
  TradingOrdersListResponse,
  TradingTradesListResponse,
} from '@/types/tradingOrders';

import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

/** Return type for useTradePageModel. */
export type TradePageModel = {
  isAuthenticated: boolean;
  isFree: boolean;
  connectOpen: boolean;
  setConnectOpen: (open: boolean) => void;
  /** Inline "Unlock vault" modal on the trade page (LIVE mode + locked vault). */
  vaultUnlockOpen: boolean;
  setVaultUnlockOpen: (open: boolean) => void;
  /** Mirrors {@link useKeyVault} `unlocked`; drives the LIVE banner's "unlock" vs "add key" copy. */
  vaultUnlocked: boolean;
  /**
   * Mirrors {@link useKeyVault} `hydrated` — flipped true after the first
   * session-restore attempt completes. Until this is true the LIVE banner
   * must NOT render its locked state (would flicker on every refresh while
   * the auto-unlock effect runs).
   */
  vaultHydrated: boolean;
  modes: TradingMode[];
  activeMode: TradingMode | null;
  setSelectedMode: (mode: TradingMode) => void;
  /** Always one of ``TRADING_MODE.*`` from active selection — API-bound ``mode`` query/body param. */
  modeStr: TradingModeKind;
  portfolio: Record<string, unknown> | undefined;
  portfolioLoading: boolean;
  portfolioError: boolean;
  side: OrderSide;
  setSide: (side: OrderSide) => void;
  amountUsd: string;
  setAmountUsd: (amountUsd: string) => void;
  orderSizeInputSemantic: OrderSizeInputSemantic;
  setOrderSizeInputSemantic: (semantic: OrderSizeInputSemantic) => void;
  price: string;
  setPrice: (price: string) => void;
  stopLoss: string;
  setStopLoss: (v: string) => void;
  takeProfit: string;
  setTakeProfit: (v: string) => void;
  orderType: OrderType;
  setOrderType: (t: OrderType) => void;
  referencePriceUsd: number | null;
  /** Resolved symbol for API (e.g. BTC/USDT). */
  orderSymbol: string;
  orderMutation: UseMutationResult<PlaceOrderResponse, Error, void, unknown>;
  resetMutation: UseMutationResult<void, Error, void, unknown>;
  marketType: MarketType;
  setMarketType: (t: MarketType) => void;
  leverage: number;
  setLeverage: (v: number) => void;
  /** @deprecated Prefer futuresSelectionAllowed — same semantics (admin may select swap). */
  canUseFutures: boolean;
  leverageTiers: LeverageTiersResponse | undefined;
  leverageMin: number;
  leverageMax: number;
  /** Paper + connected exchange lists swap support + feature flag: show Spot/Futures UI (Futures may be disabled for non-admins). */
  futuresMarketUiVisible: boolean;
  /** Admin/super_admin only for now; subscription tiers may unlock later. */
  futuresSelectionAllowed: boolean;
  /**
   * Non-null when the live-direct (browser-signed) path is active for the
   * selected mode + exchange. UI uses this to show a "Direct on {exchange}"
   * badge / latency indicator.
   */
  liveDirectKeyHint: { exchange: string; testnet: boolean; label: string } | null;
  /**
   * Non-null companion to the placement path: cancels an open order browser-direct
   * (HMAC sign + POST to exchange). Mutation hook branches on this for manual live
   * cancels (route layer rejects mode=live cancel).
   */
  liveDirectCancelOrder:
    | ((input: {
        venueOrderId: string;
        symbol: string;
        marketType: 'spot' | 'swap';
      }) => Promise<void>)
    | null;
  sltpMode: SLTPMode;
  setSltpMode: (m: SLTPMode) => void;
  maxCompoundTrades: number;
  setMaxCompoundTrades: (v: number) => void;
  minCompoundStepPct: number;
  setMinCompoundStepPct: (v: number) => void;
};

/** Return type for useTradeFormState. */
export type TradeFormState = {
  connectOpen: boolean;
  setConnectOpen: (open: boolean) => void;
  /** Inline "Unlock vault" modal on the trade page (LIVE mode + locked vault). */
  vaultUnlockOpen: boolean;
  setVaultUnlockOpen: (open: boolean) => void;
  selectedMode: TradingMode | null;
  setSelectedMode: (mode: TradingMode) => void;
  side: OrderSide;
  setSide: (side: OrderSide) => void;
  amountUsd: string;
  setAmountUsd: (v: string) => void;
  orderSizeInputSemantic: OrderSizeInputSemantic;
  setOrderSizeInputSemantic: (semantic: OrderSizeInputSemantic) => void;
  price: string;
  setPrice: (v: string) => void;
  stopLoss: string;
  setStopLoss: (v: string) => void;
  takeProfit: string;
  setTakeProfit: (v: string) => void;
  orderType: OrderType;
  setOrderType: (t: OrderType) => void;
  marketType: MarketType;
  setMarketType: (t: MarketType) => void;
  leverage: number;
  setLeverage: (v: number) => void;
  sltpMode: SLTPMode;
  setSltpMode: (m: SLTPMode) => void;
  clearOrderForm: () => void;
  maxCompoundTrades: number;
  setMaxCompoundTrades: (v: number) => void;
  minCompoundStepPct: number;
  setMinCompoundStepPct: (v: number) => void;
};

/** Return type for useTradeDemoActivityQueries. */
export type TradeDemoActivityQueriesResult = {
  tradesQuery: UseQueryResult<TradingTradesListResponse, Error>;
  ordersQuery: UseQueryResult<TradingOrdersListResponse, Error>;
};
