// =============================================================================
// Per-exchange config — SoT exports
// =============================================================================
//
// Centralized exports for FE consumers. Per-venue config modules
// (bitget.ts, eventually bybit.ts/binance.ts) hand-mirror the canonical
// yaml in `packages/shared/exchanges/<venue>.yaml`. All are validated at
// module init via {@link parseExchangeConfig}.
//
// @see docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md
// =============================================================================

export { BINANCE_CONFIG } from './binance';
export { BITGET_CONFIG } from './bitget';
export { BYBIT_CONFIG } from './bybit';
export { OKX_CONFIG } from './okx';
export {
  type AuthConfig,
  type AuthHeaderSlot,
  type BaseUrls,
  type DemoFlagHeader,
  type EnvelopeConfig,
  type ExchangeConfig,
  type PathsMap,
  type ProductType,
  type ProxyConfig,
  type SpotConfig,
  type SwapConfig,
  type WindowCaps,
  AuthConfigSchema,
  authHeader,
  BaseUrlsSchema,
  DemoFlagHeaderSchema,
  EnvelopeConfigSchema,
  ExchangeConfigSchema,
  parseExchangeConfig,
  PathsMapSchema,
  ProductTypeSchema,
  ProxyConfigSchema,
  SpotConfigSchema,
  SwapConfigSchema,
  WindowCapsSchema,
} from './schema';
