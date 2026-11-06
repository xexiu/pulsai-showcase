// =============================================================================
// OKX V5 — validated config (FE-side hand-mirror of okx.yaml)
// =============================================================================
//
// Phase 6 scaffolding. The yaml is shipped + validated against the
// canonical schema, but `EXCHANGE_CAPABILITIES.okx.liveDirect` stays
// false until the signer + response-mapping + WS parsing modules land
// (follow-up slice, gated on a real OKX demo account for curl-verify).
//
// Adding OKX live-direct after this scaffolding: drop in
// `apps/web/src/lib/live-exchange/okx/{sign,response-mapping,client,...}.ts`
// + register in `client-registry` + `signer-registry` + flip the
// capability flag. That's the success criterion of the SoT framework.
//
// @see docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md
// =============================================================================

import { parseExchangeConfig, type ExchangeConfig } from './schema';

export const OKX_CONFIG: ExchangeConfig = parseExchangeConfig({
  schema_version: 1,
  id: 'okx',
  display_name: 'OKX',
  default_fee_rate: 0.001,
  base_urls: {
    mainnet: 'https://www.okx.com',
    testnet: 'https://www.okx.com',
  },
  swap: {
    window_caps: {
      history_days: 89,
    },
    paths: {
      place_order: '/api/v5/trade/order',
      cancel_order: '/api/v5/trade/cancel-order',
      open_orders: '/api/v5/trade/orders-pending',
      orders_history: '/api/v5/trade/orders-history',
      position_history: '/api/v5/account/positions-history',
      positions: '/api/v5/account/positions',
      account: '/api/v5/account/balance',
    },
  },
  spot: {
    paths: {
      place_order: '/api/v5/trade/order',
      cancel_order: '/api/v5/trade/cancel-order',
      open_orders: '/api/v5/trade/orders-pending',
    },
  },
  auth: {
    header_names: {
      api_key: 'OK-ACCESS-KEY',
      signature: 'OK-ACCESS-SIGN',
      timestamp: 'OK-ACCESS-TIMESTAMP',
      passphrase: 'OK-ACCESS-PASSPHRASE',
    },
    needs_passphrase: true,
    demo_flag_header: {
      name: 'x-simulated-trading',
      value: '1',
    },
  },
  envelope: {
    success_code_path: 'code',
    success_code_value: '0',
    data_path: 'data',
  },
  proxy: {
    hostnames: ['www.okx.com'],
  },
  public_paths: {
    ping: '/api/v5/public/time',
  },
});
