/**
 * Outbound exchange client-order-id wire limits and prefixes (SoT).
 *
 * Mirrors `apps/api/src/shared/constants/trading.py` and carry constants.
 * Cross-runtime parity: `packages/shared/test-vectors/client_order_id_golden.json`.
 */

/** Manual / demo anchor placements (`pam-k-*` idempotent, `pam-r-*` fresh). */
export const MANUAL_ORDER_CLIENT_ID_PREFIX = 'pam' as const;

/** SHA-256 digest length embedded in `pam-k-*` / `pam-r-*` tokens. */
export const MANUAL_ORDER_CLIENT_ID_HASH_HEX_CHARS = 22;

/** Venue-safe ceiling for manual ids (Bitget/Binance/Bybit/OKX). */
export const MANUAL_ORDER_CLIENT_ID_MAX_LEN = 40;

/** CCXT unified ``params["clientOrderId"]`` wire cap (Binance strictest). */
export const CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN = 36;

/** Generated fallback when no explicit id is supplied (`pul-f-*`). */
export const CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX = 'pul-f' as const;

export const CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_FIRST = 12;
export const CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_SECOND = 10;

/** Carry leg deterministic ids (`carry-{digest}`). */
export const CARRY_CLIENT_ORDER_ID_PREFIX = 'carry' as const;

export const CARRY_CLIENT_ORDER_ID_HASH_HEX_CHARS = 24;
