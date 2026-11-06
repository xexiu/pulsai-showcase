/**
 * Paper trading domain types — exchanges, connections, trading modes, order basics.
 *
 * SoT: extracted from `trading-barrel.ts` in Phase 2.7.27 (≤400 LOC SRP).
 * Consumers import from `@/types/tradingBarrel` which re-exports.
 *
 * Aligned with backend schemas in:
 * - apps/api/src/api/v1/endpoints/exchanges_schemas.py
 * - apps/api/src/api/v1/endpoints/trading_schemas.py
 */

/** Exchange catalog item from GET /exchanges/supported. */
export type SupportedExchange = {
  id: string;
  has_testnet: boolean;
};

/** Connection status values from the backend ExchangeConnection model. */
type ExchangeConnectionStatus = 'active' | 'disconnected' | 'error' | 'pending';

/** User exchange connection from GET /exchanges (no secrets). */
export type ExchangeConnection = {
  id: string;
  exchange: string;
  status: ExchangeConnectionStatus;
  permissions: Record<string, unknown>;
  has_testnet: boolean;
  fee_rate_maker: string | null;
  fee_rate_taker: string | null;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
  /** Epic C — true when server has envelope-encrypted keys uploaded from vault. */
  has_server_keys?: boolean;
  /** Epic C — ISO-8601 expiry; null = no server keys OR legacy modal-uploaded row. */
  keys_expire_at?: string | null;
};

/** Selectable execution mode from GET /trading/modes.
 *
 * ``label_key`` + ``label_params`` are the i18n-first fields (P8-M-2 / G-4):
 * resolve the displayed copy via ``useTranslations`` against the key
 * (``dashboard.trade.modeSwitcher.{demo|paper|live}``) with the
 * params as interpolation values. ``label`` is the legacy English
 * fallback the BE still emits for backwards-compat; new FE code SHOULD
 * prefer ``label_key``.
 */
export type TradingMode = {
  id: string;
  label: string;
  label_key: string;
  label_params: Record<string, string>;
  kind: 'demo' | 'paper' | 'live';
  exchange_connection_id: string | null;
  fallback_simulated: boolean;
  /**
   * Per-mode capability from GET /trading/modes (wire key: ``TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED``).
   * Not the same as public config ``features.futures_paper_trading`` (global Spot/Futures UI kill-switch).
   */
  futures_paper_supported?: boolean;
};

/** GET /trading/modes response. */
export type TradingModesResponse = {
  modes: TradingMode[];
};

/** Market type for order requests: 'spot' (default) or 'swap' (perpetual futures). */
export type MarketType = 'spot' | 'swap';

/**
 * Órdenes "Cerrar": market-sell the FIFO-open spot lot, or swap sell to reduce a perp long.
 * Must send swap + leverage so POST /trading/orders does not default to spot (wrong wallet preflight).
 */
export type CloseOpenLongPayload = {
  btcAmountStr: string;
  marketType?: MarketType | null;
  leverage?: number | null;
};

/** Order side — buy (long) or sell (short / exit). */
export type OrderSide = 'buy' | 'sell';

/** Order type — market (immediate fill) or limit (price-conditional). */
export type OrderType = 'market' | 'limit';

/** GET /exchanges/{id}/leverage-tiers response. */
export type LeverageTiersResponse = {
  min_leverage: number;
  max_leverage: number;
  symbol: string;
  market_type: string;
};

/** POST /exchanges/connect request. */
export type ConnectExchangeRequest = {
  exchange: string;
  api_key: string;
  api_secret: string;
  passphrase?: string | null;
};

/** Known permission keys returned by CCXT `checkRequiredCredentials`. */
export type ExchangePermissionKey = 'read' | 'trade' | 'withdraw';
