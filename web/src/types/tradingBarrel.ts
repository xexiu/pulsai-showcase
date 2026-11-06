/**
 * Trading types — barrel.
 *
 * Aligned with backend schemas in:
 * - apps/api/src/api/v1/endpoints/exchanges_schemas.py
 * - apps/api/src/api/v1/endpoints/trading_schemas.py
 *
 * STRUCTURE (Phase 2.7.27 — split by concern, ≤400 LOC each):
 * - `tradingDomain.ts` → exchanges, connections, trading modes, order basics, leverage tiers
 * - `tradingOrders.ts` → order/trade/portfolio rows + place-order request
 * - `tradingHooks.ts`  → hook return types (PageModel / FormState / ActivityQueries)
 *
 * Consumers import from `@/types/tradingBarrel`.
 *
 * Epic B (RefactorHuge) — renamed from `trading-barrel.ts`; manual paper trading
 * was collapsed to FE-direct, demo persists BE-side, and live is live-direct.
 */

/** Public-config feature keys SoT — also exported from `@/types/app-config`; prefer this barrel for trading UI. */
export { FEATURES_CONFIG_KEYS, FEATURES_CONFIG_KEY_FUTURES_TRADING_UI } from '@/types/app-config';

export type { SLTPMode } from '@/types/trading-wire';

export type {
  ConnectExchangeRequest,
  ExchangeConnection,
  ExchangePermissionKey,
  LeverageTiersResponse,
  MarketType,
  CloseOpenLongPayload,
  OrderSide,
  OrderType,
  SupportedExchange,
  TradingMode,
  TradingModesResponse,
} from '@/types/tradingDomain';
export type {
  BuildPlaceOrderRequestInput,
  DemoOrderRow,
  DemoPortfolioSnapshot,
  DemoTradeRow,
  OrderRow,
  PaperOpenPositionRow,
  PaperPortfolioSnapshot,
  PlaceOrderRequest,
  PlaceOrderResponse,
  TradeRow,
  TradingOrdersListResponse,
  TradingTradesListResponse,
} from '@/types/tradingOrders';
export { isDemoPortfolioSnapshot, isPaperPortfolioSnapshot } from '@/types/tradingOrders';
export type {
  TradeDemoActivityQueriesResult,
  TradeFormState,
  TradePageModel,
} from '@/types/tradingHooks';
