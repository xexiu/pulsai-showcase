// =============================================================================
// Binance — validated config (FE-side hand-mirror of binance.yaml)
// =============================================================================
//
// Binance is OHLCV-only on PulsAI today; this config provides
// ``default_fee_rate`` + ``base_urls`` as the canonical SoT. Live-direct
// auth/envelope/proxy fields are intentionally absent — the optional
// schema accommodates BE-CCXT-only venues.
//
// @see docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md
// =============================================================================

import { parseExchangeConfig, type ExchangeConfig } from './schema';

export const BINANCE_CONFIG: ExchangeConfig = parseExchangeConfig({
  schema_version: 1,
  id: 'binance',
  display_name: 'Binance',
  default_fee_rate: 0.001,
  base_urls: {
    mainnet: 'https://api.binance.com',
    testnet: 'https://testnet.binance.vision',
  },
  // auth / envelope / proxy / swap / spot intentionally absent — no
  // live-direct path on Binance today.
  public_paths: {
    ping: '/api/v3/ping',
  },
});
