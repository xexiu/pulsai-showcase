// =============================================================================
// Bybit V5 — validated config (FE-side hand-mirror of bybit.yaml)
// =============================================================================
//
// Hand-mirrors `packages/shared/exchanges/bybit.yaml`. Same pattern as
// `bitget.ts`; parity asserted by
// `apps/api/tests/unit/shared/exchanges/test_bybit_yaml_parity.py` +
// `apps/web/tests/unit/shared/bybit-config.test.ts`.
//
// @see docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md
// =============================================================================

import { parseExchangeConfig, type ExchangeConfig } from './schema';

/**
 * Validated FE hand-mirror of `packages/shared/exchanges/bybit.yaml`.
 * Throws at module init on schema mismatch — better than silent partial
 * config at runtime.
 */
export const BYBIT_CONFIG: ExchangeConfig = parseExchangeConfig({
  schema_version: 1,
  id: 'bybit',
  display_name: 'Bybit',
  default_fee_rate: 0.001,
  base_urls: {
    mainnet: 'https://api.bybit.com',
    testnet: 'https://api-testnet.bybit.com',
  },
  swap: {
    category: 'linear',
    account_type: 'UNIFIED',
    window_caps: {
      history_days: 89,
    },
    paths: {
      place_order: '/v5/order/create',
      cancel_order: '/v5/order/cancel',
      open_orders: '/v5/order/realtime',
      orders_history: '/v5/order/history',
      position_history: '/v5/position/closed-pnl',
      positions: '/v5/position/list',
      account: '/v5/account/wallet-balance',
    },
  },
  spot: {
    category: 'spot',
    paths: {
      place_order: '/v5/order/create',
      cancel_order: '/v5/order/cancel',
      open_orders: '/v5/order/realtime',
    },
  },
  auth: {
    header_names: {
      api_key: 'X-BAPI-API-KEY',
      signature: 'X-BAPI-SIGN',
      timestamp: 'X-BAPI-TIMESTAMP',
      recv_window: 'X-BAPI-RECV-WINDOW',
    },
    needs_passphrase: false,
    sign_type: '2',
    default_recv_window_ms: 5000,
  },
  envelope: {
    success_code_path: 'retCode',
    success_code_value: 0,
    data_path: 'result',
  },
  proxy: {
    hostnames: ['api.bybit.com', 'api-testnet.bybit.com'],
  },
  public_paths: {
    ping: '/v5/market/time',
  },
});
