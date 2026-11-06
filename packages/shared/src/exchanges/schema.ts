// =============================================================================
// Per-exchange config schema (FE side — Valibot)
// =============================================================================
//
// Pin the shape of `packages/shared/exchanges/<venue>.yaml` for every
// FE-side loader. The Python side mirrors this schema in
// `apps/api/src/shared/exchanges/schema.py` (Pydantic); the two are
// hand-mirrored, parity asserted by `test_exchange_yaml_parity.py`.
//
// @see docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md §3
// =============================================================================

import * as v from 'valibot';

import { isExchangeId } from '../constants/exchanges';

export const PathsMapSchema = v.record(v.string(), v.pipe(v.string(), v.minLength(1)));
export type PathsMap = v.InferOutput<typeof PathsMapSchema>;

export const BaseUrlsSchema = v.object({
  mainnet: v.pipe(v.string(), v.url()),
  testnet: v.pipe(v.string(), v.url()),
});
export type BaseUrls = v.InferOutput<typeof BaseUrlsSchema>;

export const ProductTypeSchema = v.object({
  mainnet: v.pipe(v.string(), v.minLength(1)),
  testnet: v.pipe(v.string(), v.minLength(1)),
});
export type ProductType = v.InferOutput<typeof ProductTypeSchema>;

export const WindowCapsSchema = v.object({
  history_days: v.pipe(v.number(), v.integer(), v.minValue(1)),
});
export type WindowCaps = v.InferOutput<typeof WindowCapsSchema>;

export const SwapConfigSchema = v.object({
  /** Bitget — per-env product-type identifier (usdt-futures / SUSDT-FUTURES). */
  product_type: v.optional(ProductTypeSchema),
  /** Bybit V5 — category qualifier on every swap request (`linear` for USDT-M). */
  category: v.optional(v.pipe(v.string(), v.minLength(1))),
  /** Bybit V5 — account type used by wallet-balance endpoint (`UNIFIED`). */
  account_type: v.optional(v.pipe(v.string(), v.minLength(1))),
  /** Bitget — USDT-M margin coin. */
  margin_coin: v.optional(v.pipe(v.string(), v.minLength(1))),
  window_caps: WindowCapsSchema,
  paths: PathsMapSchema,
});
export type SwapConfig = v.InferOutput<typeof SwapConfigSchema>;

export const SpotConfigSchema = v.object({
  /** Bybit V5 category qualifier on every spot request (`spot`). */
  category: v.optional(v.pipe(v.string(), v.minLength(1))),
  paths: PathsMapSchema,
});
export type SpotConfig = v.InferOutput<typeof SpotConfigSchema>;

export const DemoFlagHeaderSchema = v.object({
  name: v.pipe(v.string(), v.minLength(1)),
  value: v.pipe(v.string(), v.minLength(1)),
});
export type DemoFlagHeader = v.InferOutput<typeof DemoFlagHeaderSchema>;

export const AuthConfigSchema = v.object({
  header_names: v.record(v.string(), v.pipe(v.string(), v.minLength(1))),
  needs_passphrase: v.boolean(),
  demo_flag_header: v.optional(DemoFlagHeaderSchema),
  /** Bybit V5 — `X-BAPI-SIGN-TYPE` value (`'2'` = HMAC-SHA256). */
  sign_type: v.optional(v.pipe(v.string(), v.minLength(1))),
  /** Bybit V5 — default `X-BAPI-RECV-WINDOW` in ms. */
  default_recv_window_ms: v.optional(v.pipe(v.number(), v.integer(), v.minValue(1))),
});
export type AuthConfig = v.InferOutput<typeof AuthConfigSchema>;

export const EnvelopeConfigSchema = v.object({
  success_code_path: v.pipe(v.string(), v.minLength(1)),
  success_code_value: v.union([v.string(), v.number()]),
  data_path: v.pipe(v.string(), v.minLength(1)),
});
export type EnvelopeConfig = v.InferOutput<typeof EnvelopeConfigSchema>;

export const ProxyConfigSchema = v.object({
  hostnames: v.pipe(v.array(v.pipe(v.string(), v.minLength(1))), v.minLength(1)),
});
export type ProxyConfig = v.InferOutput<typeof ProxyConfigSchema>;

/**
 * Unauthenticated REST endpoints used for admin observability. `ping` is
 * the lowest-cost public endpoint (server time / status). Used by the
 * `/admin/exchanges` health page; never reached by user-facing trade flows.
 */
export const PublicPathsSchema = v.object({
  ping: v.optional(v.pipe(v.string(), v.minLength(1))),
});
export type PublicPaths = v.InferOutput<typeof PublicPathsSchema>;

/**
 * Top-level config for one exchange. Matches the structure of
 * `packages/shared/exchanges/<venue>.yaml`.
 *
 * Notes:
 * - `schema_version` is `1` literal — bump only on a breaking field change
 *   so existing yaml files fail loud instead of silent-drift.
 * - `id` is checked via `isExchangeId` at module-init via the loader
 *   helper, not in the schema itself (avoids a circular dep between
 *   schema.ts and the canonical id list).
 */
export const ExchangeConfigSchema = v.object({
  schema_version: v.literal(1),
  id: v.pipe(v.string(), v.minLength(1)),
  display_name: v.pipe(v.string(), v.minLength(1)),
  default_fee_rate: v.pipe(v.number(), v.minValue(0), v.maxValue(1)),
  base_urls: BaseUrlsSchema,
  swap: v.optional(SwapConfigSchema),
  spot: v.optional(SpotConfigSchema),
  /** Optional: venues without a live-direct path (Binance — BE OHLCV
   *  only via CCXT) can omit auth shape. */
  auth: v.optional(AuthConfigSchema),
  /** Optional: see `auth`. */
  envelope: v.optional(EnvelopeConfigSchema),
  /** Optional: venues we never forward to via the Edge proxy can omit. */
  proxy: v.optional(ProxyConfigSchema),
  /** Optional: unauthenticated paths for admin observability (Epic H). */
  public_paths: v.optional(PublicPathsSchema),
});
export type ExchangeConfig = v.InferOutput<typeof ExchangeConfigSchema>;

/**
 * Parse + validate a raw object against {@link ExchangeConfigSchema} AND
 * cross-check that the `id` field is a known {@link ExchangeId}. Throws on
 * any schema violation or unknown id — module init fails loud, no silent
 * partial config.
 */
export function parseExchangeConfig(raw: unknown): ExchangeConfig {
  const parsed = v.parse(ExchangeConfigSchema, raw);

  if (!isExchangeId(parsed.id)) {
    throw new Error(
      `Exchange config id="${parsed.id}" is not in the canonical ExchangeId list. ` +
        `Update packages/shared/src/constants/exchanges.ts EXCHANGE_IDS first.`
    );
  }

  return parsed;
}

/**
 * Standard slot keys for auth headers. Every venue exposes a subset of
 * these — `api_key`, `signature`, and `timestamp` are universal; the
 * others are venue-specific (`passphrase` on Bitget/OKX, `recv_window`
 * on Bybit V5).
 */
export type AuthHeaderSlot = 'api_key' | 'signature' | 'timestamp' | 'passphrase' | 'recv_window';

/**
 * Read a named auth-header from a venue config. Throws when the slot is
 * not present in yaml — callers that DEPEND on a slot (Bitget's signer
 * requires `passphrase`, Bybit's requires `recv_window`) get a loud
 * module-init failure if the yaml is missing the key, instead of a
 * silent runtime mistake.
 */
export function authHeader(auth: AuthConfig, slot: AuthHeaderSlot): string {
  const name = auth.header_names[slot];

  if (name == null) {
    throw new Error(
      `Auth header slot "${slot}" missing from yaml.auth.header_names — ` +
        `every venue must declare api_key/signature/timestamp at minimum.`
    );
  }

  return name;
}
