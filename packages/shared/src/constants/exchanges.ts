// =============================================================================
// Exchange canonical SoT — IDs + capability matrix
// =============================================================================
//
// Single source of truth for "which exchanges does PulsAI know about, and
// what can each one do?". Both FE and BE derive from this:
//
//   - FE: `apps/web/src/lib/live-exchange/types.ts` re-exports
//     `LiveDirectExchangeId` (browser-direct REST/WS path).
//   - BE: `apps/api/src/shared/constants/exchanges.py` mirrors this list
//     (hand-mirror; enforced by a parity test on both sides — see
//     `apps/web/tests/unit/shared/exchanges.test.ts` and the sibling
//     `apps/api/tests/unit/shared/constants/test_exchange_ids_parity.py`).
//
// HOW TO ADD AN EXCHANGE:
//   1. Add the CCXT id to `EXCHANGE_IDS` (lowercase, matching ccxt-exchange).
//   2. Add a row to `EXCHANGE_CAPABILITIES`.
//   3. If liveDirect=true, add the id to `LIVE_DIRECT_EXCHANGE_IDS`.
//   4. Mirror the same edit in `apps/api/src/shared/constants/exchanges.py`
//      (parity test will fail until you do).
//
// See `docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md` for the architectural
// rationale and the migration roadmap (Phases 1-6).
//
// =============================================================================

/**
 * Canonical lowercase CCXT-style exchange identifiers PulsAI knows about.
 *
 * Ordering: implemented liveDirect first, then OHLCV-only, then
 * user-connectable-but-not-implemented. Tests are order-agnostic so adding
 * a new venue in any position is safe.
 *
 * Frozen at module init so callers can't mutate the canonical list.
 */
export const EXCHANGE_IDS = Object.freeze([
  'binance',
  'bitget',
  'bybit',
  'okx',
  'coinbase',
  'kraken',
] as const);

/**
 * Union of all canonical exchange ids. Use this anywhere a function/type
 * needs to accept "any exchange PulsAI knows about" — not just the narrow
 * liveDirect subset.
 */
export type ExchangeId = (typeof EXCHANGE_IDS)[number];

/**
 * Per-exchange capability metadata. Every flag is a runtime fact about
 * what PulsAI's code can do today — NOT a wishlist. Flipping a flag from
 * false to true is a code change in the relevant subsystem (client,
 * signer, fetcher), not just a yaml/config update.
 */
export type ExchangeCapabilities = {
  /**
   * PulsAI has REST + WS code to talk directly from the browser
   * (Tealstreet-style live-direct path).
   */
  liveDirect: boolean;
  /**
   * PulsAI uses CCXT on the BE for OHLCV fetch + (optionally) paper-fill
   * simulation against this venue.
   */
  ohlcv: boolean;
  /**
   * Venue exposes a sandbox/testnet suitable for paper / demo keys.
   * False for venues that only have mainnet.
   */
  testnet: boolean;
  /**
   * Venue requires an API passphrase in addition to key + secret (Bitget,
   * OKX). FE key-vault + BE connection-service surface this in the form.
   */
  needsPassphrase: boolean;
};

/**
 * Capability matrix. One row per `ExchangeId`; TypeScript's `Record<K, V>`
 * guarantees every id has a row (compile-time exhaustiveness).
 *
 * Frozen at module init.
 */
export const EXCHANGE_CAPABILITIES: Readonly<Record<ExchangeId, ExchangeCapabilities>> =
  Object.freeze({
    binance: { liveDirect: false, ohlcv: true, testnet: true, needsPassphrase: false },
    bitget: { liveDirect: true, ohlcv: true, testnet: true, needsPassphrase: true },
    bybit: { liveDirect: true, ohlcv: false, testnet: true, needsPassphrase: false },
    // OKX V5: signer + client + mappers shipped (Phase 6). Marked
    // ``liveDirect: true`` because the framework wiring is complete —
    // client-registry + signer-registry resolve OKX. **Note:** the
    // implementation is doc-based, not curl-verified end-to-end.
    okx: { liveDirect: true, ohlcv: false, testnet: true, needsPassphrase: true },
    coinbase: { liveDirect: false, ohlcv: false, testnet: false, needsPassphrase: false },
    kraken: { liveDirect: false, ohlcv: false, testnet: false, needsPassphrase: false },
  });

/**
 * Narrow subset of `EXCHANGE_IDS` whose `liveDirect` capability is `true`.
 *
 * Declared as a literal-typed tuple so callers get the narrowest possible
 * TypeScript union (`'bitget' | 'bybit'` today) instead of the broader
 * `ExchangeId`. `satisfies` enforces that every entry is a valid
 * `ExchangeId` at compile time — drift between this list and
 * `EXCHANGE_CAPABILITIES[*].liveDirect` is caught by a unit test.
 */
export const LIVE_DIRECT_EXCHANGE_IDS = [
  'bitget',
  'bybit',
  'okx',
] as const satisfies readonly ExchangeId[];

/** Narrow union of exchange ids supporting the browser-direct REST/WS path. */
export type LiveDirectExchangeId = (typeof LIVE_DIRECT_EXCHANGE_IDS)[number];

/**
 * Runtime type guard for `ExchangeId`. Use at any boundary that receives
 * a string from outside the type system (URL params, form input, BE
 * payload) before casting.
 */
export function isExchangeId(s: string): s is ExchangeId {
  return (EXCHANGE_IDS as readonly string[]).includes(s);
}

/**
 * Runtime type guard for `LiveDirectExchangeId`. Strictly narrower than
 * `isExchangeId` — returns false for non-liveDirect venues.
 */
export function isLiveDirectExchangeId(s: string): s is LiveDirectExchangeId {
  return (LIVE_DIRECT_EXCHANGE_IDS as readonly string[]).includes(s);
}
