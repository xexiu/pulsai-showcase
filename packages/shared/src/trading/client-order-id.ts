/**
 * Outbound client order id policy (FE SoT).
 *
 * Algorithms mirror `apps/api/src/domain/services/manual_order_client_id.py` and
 * `ccxt_order_client_id.py`. Parity locked by `test-vectors/client_order_id_golden.json`.
 */

import {
  CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_FIRST,
  CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_SECOND,
  CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX,
  CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN,
  MANUAL_ORDER_CLIENT_ID_HASH_HEX_CHARS,
  MANUAL_ORDER_CLIENT_ID_MAX_LEN,
  MANUAL_ORDER_CLIENT_ID_PREFIX,
} from '../constants/trading-client-order-id';

export type BuildManualOrderClientOrderIdInput = {
  connectionId: string;
  symbol: string;
  side: string;
  orderType: string;
  /** Normalized HTTP Idempotency-Key; omit for a fresh random `pam-r-*` id. */
  normalizedKey: string | null;
};

function truncateVenueSafe(value: string, maxLen: number): string {
  return value.length <= maxLen ? value : value.slice(0, maxLen);
}

async function sha256HexPrefix(input: string, len: number): Promise<string> {
  const subtle = globalThis.crypto?.subtle;

  if (subtle == null) {
    throw new Error('Web Crypto is unavailable; cannot build deterministic clientOrderId');
  }

  const digest = await subtle.digest('SHA-256', new TextEncoder().encode(input));
  const hex = Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');

  return hex.slice(0, len);
}

function randomHex(chars: number): string {
  const bytes = new Uint8Array(Math.ceil(chars / 2));
  globalThis.crypto.getRandomValues(bytes);

  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, chars);
}

/**
 * Deterministic `pam-k-*` when `normalizedKey` is set; otherwise fresh `pam-r-*`.
 */
export async function buildManualOrderClientOrderId(
  input: BuildManualOrderClientOrderIdInput
): Promise<string> {
  if (input.normalizedKey != null && input.normalizedKey.trim() !== '') {
    const seed = [
      input.connectionId,
      input.normalizedKey.trim(),
      input.symbol.toLowerCase(),
      input.side.toLowerCase(),
      input.orderType.toLowerCase(),
    ].join('|');
    const token = await sha256HexPrefix(seed, MANUAL_ORDER_CLIENT_ID_HASH_HEX_CHARS);

    return truncateVenueSafe(
      `${MANUAL_ORDER_CLIENT_ID_PREFIX}-k-${token}`,
      MANUAL_ORDER_CLIENT_ID_MAX_LEN
    );
  }

  const token = randomHex(MANUAL_ORDER_CLIENT_ID_HASH_HEX_CHARS);

  return truncateVenueSafe(
    `${MANUAL_ORDER_CLIENT_ID_PREFIX}-r-${token}`,
    MANUAL_ORDER_CLIENT_ID_MAX_LEN
  );
}

/**
 * Return a non-empty venue-safe client id for every outbound placement.
 */
export function ensureOutboundClientOrderId(explicit: string | null | undefined): string {
  if (explicit != null) {
    const trimmed = explicit.trim();

    if (trimmed !== '') {
      return truncateVenueSafe(trimmed, CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN);
    }
  }

  const a = randomHex(CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_FIRST);
  const b = randomHex(CCXT_FALLBACK_CLIENT_ORDER_ID_ENTROPY_HEX_CHARS_SECOND);

  return truncateVenueSafe(
    `${CCXT_FALLBACK_CLIENT_ORDER_ID_PREFIX}-${a}-${b}`,
    CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN
  );
}

export type ResolvePlacementClientOrderIdInput = BuildManualOrderClientOrderIdInput;

/**
 * Single resolver for manual/demo/live-direct placements before hitting a venue adapter.
 */
export async function resolvePlacementClientOrderId(
  input: ResolvePlacementClientOrderIdInput
): Promise<string> {
  return buildManualOrderClientOrderId(input);
}
