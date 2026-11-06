/**
 * Paper trading order / trade / portfolio types.
 *
 * SoT: extracted from `trading-barrel.ts` in Phase 2.7.27 (≤400 LOC SRP).
 * Consumers import from `@/types/tradingBarrel` which re-exports.
 */

import type {
  FuturesPositionModeKind,
  OrderSizeInputSemantic,
  SLTPMode,
} from '@/types/trading-wire';
import type { MarketType } from '@/types/tradingDomain';

/** POST /trading/orders request. */
export type PlaceOrderRequest = {
  mode: 'demo' | 'paper' | 'live';
  exchange_connection_id?: string | null;
  side: 'buy' | 'sell';
  symbol: string;
  price: string;
  /** Backend default `market`. Use `limit` for demo resting limits (pending until mark crosses). */
  order_execution?: 'market' | 'limit';
  amount_usd?: string | null;
  amount_btc?: string | null;
  stop_loss_price?: string | null;
  take_profit_price?: string | null;
  /** SL/TP pricing mode: absolute or percentage (for compound/DCA recalculation). */
  sltp_mode?: SLTPMode;
  /** Original SL offset % (stored for compound recalc; e.g. -5.0 for long, +5.0 for short). */
  sl_percentage?: string | null;
  /** Original TP offset % (stored for compound recalc; e.g. +10.0 for long, -10.0 for short). */
  tp_percentage?: string | null;
  /** Market type: 'spot' (default) or 'swap' (perpetual futures). */
  market_type?: MarketType;
  /** Required when market_type='swap'. */
  leverage?: number;
  /** Paper mode: max compound fills (1–10); BE enforces hard cap. */
  max_compound_trades?: number;
  /** Paper mode: optional min % vs last fill for extra compound legs (0–100). */
  min_compound_step_pct?: number;
  /** Paper-only: manual vs policy-assisted (persisted on `paper_orders.paper_order_intent`). */
  paper_order_intent?: 'manual' | 'policy_assisted' | null;
  /**
   * Optional audit tag for persistence (e.g. `fixed_holding`) — matches BE `TradingOrderRequest.exit_strategy` (max 32 chars; Valibot enforces).
   */
  exit_strategy?: string | null;
  /**
   * Paper/live swap market only: venue must reduce position (not open flip).
   * Omitted or false for opens; true for Órdenes **Cerrar** on perps.
   */
  reduce_only?: boolean | null;
};

/** POST /trading/orders response. */
export type PlaceOrderResponse = {
  result: Record<string, unknown>;
};

/** Structured demo portfolio snapshot from GET /trading/portfolio (mode=demo). */
export type DemoPortfolioSnapshot = {
  portfolio_id: string;
  balance_usd: string;
  btc_balance: string;
  usd_locked: string;
  version: number;
  bracket_stop_loss_usd?: string | null;
  bracket_take_profit_usd?: string | null;
  stats_trade_count?: number;
  stats_fees_paid_usd?: string;
  stats_realized_pnl_usd?: string;
  stats_position_cost_basis_usd?: string;
};

/** Type guard: checks whether portfolio payload is a demo snapshot. */
export function isDemoPortfolioSnapshot(p: Record<string, unknown>): p is DemoPortfolioSnapshot {
  return typeof p['balance_usd'] === 'string' && typeof p['btc_balance'] === 'string';
}

/** Open paper position row from GET /trading/portfolio (mode=paper). */
export type PaperOpenPositionRow = {
  position_id: string;
  symbol: string;
  side: string;
  market_type: string;
  fill_count: number;
  compound_cap: number;
  compound_remaining: number;
  stop_loss_price?: string | null;
  take_profit_price?: string | null;
};

/** Paper portfolio payload from GET /trading/portfolio (mode=paper). */
export type PaperPortfolioSnapshot = {
  mode: 'paper';
  exchange_connection_id: string;
  balance: Record<string, unknown>;
  open_positions: PaperOpenPositionRow[];
  /** Venue-sourced USDS-M position mode; read-only in UI. */
  futures_position_mode?: FuturesPositionModeKind;
};

/** Type guard: paper portfolio with optional open positions for compound UI. */
export function isPaperPortfolioSnapshot(p: Record<string, unknown>): p is PaperPortfolioSnapshot {
  return p['mode'] === 'paper' && typeof p['exchange_connection_id'] === 'string';
}

/** Unified trade row from GET /trading/trades (demo + paper). */
export type TradeRow = {
  id: string;
  order_id: string | null;
  symbol: string;
  side: 'buy' | 'sell';
  btc_amount: string;
  usd_amount: string;
  price: string;
  fee: string;
  created_at: string;
  realized_pnl_usd?: string | null;
  avg_entry_price_usd?: string | null;
  /** Quote-per-base reference at fill boundary (wire USD string); null when not captured. */
  reference_price_usd?: string | null;
  /** ISO-8601 UTC when reference_price_usd was captured; null when absent. */
  reference_price_at?: string | null;
  market_type?: MarketType | null;
  leverage?: number | null;
  ccxt_order_id?: string | null;
  /** CCXT / venue per-fill ledger id when exposed (Historial dedupe). */
  venue_trade_id?: string | null;
};

/** @deprecated Use TradeRow — alias kept for backward compatibility. */
export type DemoTradeRow = TradeRow;

export type TradingTradesListResponse = {
  trades: TradeRow[];
};

/** Unified order row from GET /trading/orders (demo + paper). */
export type OrderRow = {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  status: string;
  amount_usd: string | null;
  amount_btc: string | null;
  limit_price: string | null;
  /** Paper/live: venue-reported average fill from CCXT when persisted. */
  fill_price?: string | null;
  /** Demo: pending limit bracket; paper/live: exchange may expose protective prices. */
  stop_loss_price?: string | null;
  take_profit_price?: string | null;
  /** Paper/live: CCXT execution fee cost when persisted; demo omits. */
  fee?: string | null;
  created_at: string;
  updated_at: string;
  market_type?: MarketType | null;
  leverage?: number | null;
  ccxt_order_id?: string | null;
  /** Paper/live: CCXT clientOrderId echoed by the venue (correlation vs venue order id). */
  venue_client_order_id?: string | null;
  /** Paper: open aggregate position id when this order is attached (swap / compound). */
  paper_position_id?: string | null;
  paper_order_intent?: string | null;
  exit_strategy?: string | null;
  /** Paper/live: CCXT unified position metrics after post-fill reconcile (swap). */
  venue_entry_price?: string | null;
  venue_mark_price?: string | null;
  venue_liquidation_price?: string | null;
  venue_initial_margin?: string | null;
  venue_unrealized_pnl?: string | null;
  venue_breakeven_price?: string | null;
  venue_realized_pnl?: string | null;
  /** CCXT unified ``percentage`` (roe-style vs initial margin). */
  venue_roe_pct?: string | null;
  /** e.g. Bitget keepMarginRate as decimal. */
  venue_maintenance_margin_rate?: string | null;
  /** cross | isolated — from exchange snapshot. */
  venue_margin_mode?: string | null;
};

/** @deprecated Use OrderRow — alias kept for backward compatibility. */
export type DemoOrderRow = OrderRow;

export type TradingOrdersListResponse = {
  orders: OrderRow[];
};

/** Input for `buildPlaceOrderRequestOrThrow` — maps form state to API body. */
export type BuildPlaceOrderRequestInput = {
  orderType: 'market' | 'limit';
  limitPrice: string;
  livePrice: number | null;
  amountUsd: string;
  /**
   * How the amount field is interpreted before building ``amount_btc`` / demo ``amount_usd``.
   * @see ORDER_SIZE_INPUT_SEMANTIC — default is notional USD (legacy behavior).
   */
  orderSizeInputSemantic?: OrderSizeInputSemantic;
  modeStr: string;
  connectionId: string | null | undefined;
  side: 'buy' | 'sell';
  orderSymbol: string;
  stopLoss: string;
  takeProfit: string;
  marketType?: MarketType | undefined;
  leverage?: number | undefined;
  sltpMode?: SLTPMode | undefined;
  /** Paper mode only — max compound fills for this order. */
  maxCompoundTrades?: number | undefined;
  /** Paper mode only — min favorable % from last fill for extra legs (optional). */
  minCompoundStepPct?: number | undefined;
  /** Paper mode: persisted on the order row for audit (manual vs policy-assisted). */
  paperOrderIntent?: 'manual' | 'policy_assisted' | undefined;
  /**
   * Optional venue exchange id (e.g. ``bitget``) for FE bracket gating on spot.
   * BE SoT remains authoritative; when set and unsupported, SL/TP fields are omitted.
   */
  venueExchangeId?: string | null | undefined;
  /**
   * Demo spot market sell only: exact base size (e.g. FIFO lot from `openLongBtcByOrderIdAfterFifo`).
   * Sending `amount_usd` instead causes USD rounding → backend BTC can be slightly below the buy lot,
   * leaving FIFO dust so the order stays on Órdenes after close.
   */
  demoMarketSellAmountBtc?: string | undefined;
  /**
   * When true and CCXT path is swap market (paper/live), sets `reduce_only` on the API body.
   * Set by swap close builders (`buildMarketSellPlaceOrderFromBtcAmount`); not a user toggle.
   */
  reduceOnly?: boolean | undefined;
};
