// =============================================================================
// Symbol Registry - the ONE shared copy of the supported trading symbols
// =============================================================================
//
// The backend is the SoT (DEFAULT_SUPPORTED_SYMBOL_VALUES in
// apps/api/src/shared/constants/trading.py) and serves the live list via GET /config/public.
// A TypeScript union is compile-time, so the shared package keeps this static copy — and only
// this one: TradingSymbol, TRADING_SYMBOLS and TradingSymbolSchema all derive from it.
//
// WHY: on 2026-09-11 four hand-kept copies existed and the TRADING_SYMBOLS fallback listed 3
// symbols while the backend served 5. Drift is now caught by
// apps/api/tests/unit/shared/constants/test_symbol_frontend_parity.py.
//
// Order matters: the first symbol is the product default.

export const DEFAULT_SUPPORTED_SYMBOLS = [
  'BTC/USDT',
  'ETH/USDT',
  'SOL/USDT',
  'XRP/USDT',
  'BNB/USDT',
] as const;

export type RegistrySymbol = (typeof DEFAULT_SUPPORTED_SYMBOLS)[number];
