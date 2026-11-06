/**
 * Paper / demo trading — order form, sizing, and order wire values (SoT).
 *
 * §12 CODING_STANDARDS: business/config values in constants; no magic numbers in components.
 */

/**
 * Spot vs perpetual swap — order form / API (SoT with backend).
 * BE SoT: `apps/api/src/shared/constants/exchanges.py` (`MARKET_TYPE_SPOT`, `MARKET_TYPE_SWAP`).
 */
export const MARKET_TYPE = { SPOT: 'spot', SWAP: 'swap' } as const;

/**
 * Venue USDS-M account position mode — portfolio JSON + read-only UI (swap close uses BE-resolved mode).
 * BE SoT: `apps/api/src/shared/constants/futures_position_mode.py`.
 */
export const FUTURES_POSITION_MODE = {
  ONE_WAY: 'one_way',
  HEDGE: 'hedge',
  UNKNOWN: 'unknown',
} as const;

export type FuturesPositionModeKind =
  (typeof FUTURES_POSITION_MODE)[keyof typeof FUTURES_POSITION_MODE];

/**
 * ``GET /trading/portfolio`` field merged by paper/live handlers.
 * BE SoT: ``PORTFOLIO_FIELD_FUTURES_POSITION_MODE`` in ``futures_position_mode.py``.
 */
export const PORTFOLIO_JSON_KEY_FUTURES_POSITION_MODE = 'futures_position_mode' as const;

export function isFuturesPositionMode(value: unknown): value is FuturesPositionModeKind {
  return (
    value === FUTURES_POSITION_MODE.ONE_WAY ||
    value === FUTURES_POSITION_MODE.HEDGE ||
    value === FUTURES_POSITION_MODE.UNKNOWN
  );
}

/**
 * Spot SL/TP via venue plan/conditional orders (paper + live).
 * BE SoT: `apps/api/src/infrastructure/exchange/spot_brackets/default_registry.py`.
 */
export const SPOT_PLAN_BRACKET_SUPPORTED_EXCHANGE_IDS = ['bitget'] as const;

/**
 * Order side — order form / API.
 * BE SoT: `apps/api/src/shared/constants/paper_trading.py` (`ORDER_SIDE_BUY`, `ORDER_SIDE_SELL`).
 */
export const ORDER_SIDE = { BUY: 'buy', SELL: 'sell' } as const;

/**
 * Market vs limit — order form / API.
 * BE SoT: `apps/api/src/shared/constants/paper_trading.py` (`ORDER_TYPE_MARKET`, `ORDER_TYPE_LIMIT`).
 */
export const ORDER_TYPE = { MARKET: 'market', LIMIT: 'limit' } as const;

/**
 * Paper order rows mirrored from the venue open-order book (import / WS materialize).
 * Filled exchange-native legs (e.g. Bitget SL hit → market fill) use this; Órdenes should
 * only show PulsAI-managed exposure + resting venue orders, not those closed fills.
 *
 * BE SoT: `apps/api/src/application/services/paper_trading/venue_open_order_import.py`.
 */
export const PAPER_ORDER_EXIT_STRATEGY_VENUE_OPEN_ORDER_MIRROR = 'venue_open_order_mirror' as const;

/**
 * Persisted ``paper_orders.exit_strategy`` wire tags the UI maps to readable labels.
 * BE SoT includes ``venue_mirror_import`` in ``apps/api/src/shared/constants/paper_trading.py``.
 */
export const PAPER_ORDER_EXIT_STRATEGY_WIRE = {
  VENUE_MIRROR_IMPORT: 'venue_mirror_import',
  SIGNAL_EXIT: 'signal_exit',
  SPOT_SELL: 'sell',
  RAW_SIGNAL: 'raw_signal',
} as const;

/**
 * How the amount field maps to venue/CCXT sizing for paper/live (and base for demo).
 *
 * - **notional_usd** — quote notional (e.g. USDT); FE derives ``amount_btc`` as notional ÷ ref price
 *   (matches Bitget-style “≈ N USDT position” when ref tracks mark/limit).
 * - **margin_usd** — swap only: user-entered collateral (iso margin before BE headroom); effective
 *   notional = margin × leverage (same wire as today: still POST ``amount_btc`` only).
 * - **base_asset** — explicit base size; FE sends ``amount_btc`` / demo ``amount_btc`` directly.
 *
 * BE SoT: ``TradingOrderRequest`` rejects ``amount_usd`` for paper/live; only ``amount_btc`` is sent
 * (``apps/api/src/api/v1/endpoints/trading_schemas/order.py``).
 */
export const ORDER_SIZE_INPUT_SEMANTIC = {
  NOTIONAL_USD: 'notional_usd',
  MARGIN_USD: 'margin_usd',
  BASE_ASSET: 'base_asset',
} as const;

export type OrderSizeInputSemantic =
  (typeof ORDER_SIZE_INPUT_SEMANTIC)[keyof typeof ORDER_SIZE_INPUT_SEMANTIC];

/** Default pair for order form and API (matches backend default). */
export const TRADING_DEFAULT_ORDER_SYMBOL = 'BTC/USDT' as const;

/**
 * Synthetic `position_id` for demo spot bracket SL/TP lines on the trade chart.
 * Not a DB row — FE chart overlay only (`selectTradeChartTpSlPositions`).
 */
export const TRADE_CHART_DEMO_BRACKET_POSITION_ID = 'demo-long-bracket' as const;

/** Futures leverage app defaults (matches backend MIN_LEVERAGE / MAX_LEVERAGE). */
export const LEVERAGE_MIN_DEFAULT = 3;
export const LEVERAGE_MAX_DEFAULT = 100;
export const LEVERAGE_DEFAULT = 3;

/**
 * Compound / DCA max fills per order — must stay aligned with backend
 * `src/shared/constants/compound_limits.py` (single SoT for paper + backtest).
 */

export const COMPOUND_MAX_TRADES = 10;
export const COMPOUND_DEFAULT_MAX_TRADES = 3;
/** Backtest API: 0 = compound path off (legacy single-fill). */
export const COMPOUND_BACKTEST_DISABLED = 0;

/** User API phased unlock — aligned with BE `compound_limits.py` CERT caps (the cert's DCA depths reach 5). */
export const LEVERAGED_COMPOUND_USER_MAX_TRADES = 5;
export const LEVERAGED_COMPOUND_USER_MAX_LEVERAGE = 6;

/** Optional min % step vs last fill requires at least two possible compound fills (BE/paper parity). */
export const COMPOUND_MIN_MAX_TRADES_FOR_MIN_STEP_PCT = 2;

/**
 * When ``max_compound_trades`` ≥ ``COMPOUND_MIN_MAX_TRADES_FOR_MIN_STEP_PCT``, paper/live HTTP
 * and the order form require at least this step % (aligned with
 * ``apps/api/src/shared/constants/compound_limits.py``).
 */
export const COMPOUND_MIN_COMPOUND_STEP_PCT = 0.5;

/**
 * Tolerate JS float dust when comparing `minCompoundStepPct` to the 0.5% floor
 * (e.g. `0.5 - 1e-9` from sliders). Wider than :data:`TRADING_NUMERIC_EPSILON`.
 */
export const COMPOUND_MIN_STEP_PCT_FLOOR_EPSILON = 1e-8;

/** UI cap (NumberInput max) for min compound step % — same scale as other % fields in trade/backtest. */
export const COMPOUND_MIN_STEP_PCT_UI_MAX = 100;

/** Min compound step % when the ladder is off or below ``COMPOUND_MIN_MAX_TRADES_FOR_MIN_STEP_PCT``. */
export const COMPOUND_MIN_STEP_PCT_OFF_VALUE = 0;

/**
 * Paper order status values.
 * BE SoT: `apps/api/src/shared/constants/paper_trading.py` (`PAPER_ORDER_STATUS_*`).
 */
export const PAPER_ORDER_STATUS = {
  PENDING: 'pending',
  FILLED: 'filled',
  PARTIALLY_FILLED: 'partially_filled',
  CANCELLED: 'cancelled',
  FAILED: 'failed',
  FILL_UNKNOWN: 'fill_unknown',
} as const;
/**
 * Paper order intent — manual user action vs policy/automation-assisted.
 * BE SoT: `apps/api/src/shared/constants/paper_trading.py` (`PAPER_ORDER_INTENT_MANUAL`, `PAPER_ORDER_INTENT_POLICY_ASSISTED`).
 */

/**
 * SL/TP pricing mode.
 * BE SoT: `apps/api/src/shared/constants/paper_trading.py` (`SLTPMode`).
 */
export const SLTP_MODE = {
  ABSOLUTE: 'absolute',
  PERCENTAGE: 'percentage',
} as const;
