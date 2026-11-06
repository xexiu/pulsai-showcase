/** Paper trading wire enums (types-only SoT; runtime consts in utils/constants). */

export type TradingModeKind = 'demo' | 'paper' | 'live';

export type FuturesPositionModeKind = 'one_way' | 'hedge' | 'unknown';

export type SLTPMode = 'absolute' | 'percentage';

export type OrderSizeInputSemantic = 'notional_usd' | 'margin_usd' | 'base_asset';
