// =============================================================================
// Bitget V2 — validated config (FE-side hand-mirror of bitget.yaml)
// =============================================================================
//
// Hand-mirrors `packages/shared/exchanges/bitget.yaml`. The BE loads the
// yaml directly via PyYAML; the FE bundle can't (Webpack/Turbopack don't
// support runtime yaml load without per-app config), so we hand-mirror
// here and assert byte-equality via a parity test:
//   apps/api/tests/unit/shared/exchanges/test_bitget_yaml_parity.py
//
// Future: drop this hand-mirror in favor of a build-time codegen step
// (`pnpm shared:codegen` reads yaml → emits this TS module). See Epic A
// roadmap §4 Phase 5 / §5.
//
// Editing rules:
//   1. Update `packages/shared/exchanges/bitget.yaml` first.
//   2. Mirror the change here.
//   3. Run tests — parity test must pass on both FE and BE.
//
// @see docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md
// =============================================================================

import { parseExchangeConfig, type ExchangeConfig } from './schema';

/**
 * Hand-mirror of `packages/shared/exchanges/bitget.yaml`. Validated at
 * module load against the canonical schema — if a field is missing or
 * malformed, the entire bundle fails to initialize (better than silent
 * partial config at runtime).
 */
export const BITGET_CONFIG: ExchangeConfig = parseExchangeConfig({
  schema_version: 1,
  id: 'bitget',
  display_name: 'Bitget',
  default_fee_rate: 0.001,
  base_urls: {
    mainnet: 'https://api.bitget.com',
    testnet: 'https://api.bitget.com',
  },
  swap: {
    product_type: {
      mainnet: 'usdt-futures',
      testnet: 'SUSDT-FUTURES',
    },
    margin_coin: 'USDT',
    window_caps: {
      history_days: 89,
    },
    paths: {
      place_order: '/api/v2/mix/order/place-order',
      cancel_order: '/api/v2/mix/order/cancel-order',
      open_orders: '/api/v2/mix/order/orders-pending',
      orders_history: '/api/v2/mix/order/orders-history',
      position_history: '/api/v2/mix/position/history-position',
      positions: '/api/v2/mix/position/all-position',
      account: '/api/v2/mix/account/account',
    },
  },
  spot: {
    paths: {
      place_order: '/api/v2/spot/trade/place-order',
      cancel_order: '/api/v2/spot/trade/cancel-order',
      open_orders: '/api/v2/spot/trade/unfilled-orders',
    },
  },
  auth: {
    header_names: {
      api_key: 'ACCESS-KEY',
      signature: 'ACCESS-SIGN',
      timestamp: 'ACCESS-TIMESTAMP',
      passphrase: 'ACCESS-PASSPHRASE',
    },
    needs_passphrase: true,
    demo_flag_header: {
      name: 'paptrading',
      value: '1',
    },
  },
  envelope: {
    success_code_path: 'code',
    success_code_value: '00000',
    data_path: 'data',
  },
  proxy: {
    hostnames: ['api.bitget.com'],
  },
  public_paths: {
    ping: '/api/v2/public/time',
  },
});
