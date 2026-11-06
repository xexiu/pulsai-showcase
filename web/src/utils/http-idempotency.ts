/**
 * HTTP idempotency helpers — FE SoT aligned with BE `http_idempotency.py`.
 */

import type { AdminConfigMutationOptions } from '@/types/admin-config-with-etag';
import { buildHttpIdempotencyKey } from '@/utils/build-http-idempotency-key';
import {
  HTTP_HEADER_IDEMPOTENT_REPLAYED,
  HTTP_HEADER_IDEMPOTENT_REPLAYED_VALUE_TRUE,
  HTTP_IDEMPOTENCY_KEY_HEADER,
  HTTP_IDEMPOTENCY_KEY_MAX_LEN,
} from '@/utils/constants/httpIdempotency';
import { ifMatchRequestHeaders } from '@/utils/http-concurrency';

export type AdminHttpMutationOptions = {
  signal?: AbortSignal;
  /** When omitted, a fresh key is generated per request. */
  idempotencyKey?: string | null;
};

function mergeRequestHeaders(
  ...parts: (HeadersInit | undefined)[]
): Record<string, string> | undefined {
  const merged: Record<string, string> = {};

  for (const part of parts) {
    if (part == null) {
      continue;
    }

    const entries =
      part instanceof Headers
        ? Array.from(part.entries())
        : Object.entries(part as Record<string, string>);

    for (const [key, value] of entries) {
      merged[key] = value;
    }
  }

  return Object.keys(merged).length > 0 ? merged : undefined;
}

function normalizeIdempotencyKey(key: string): string {
  const trimmed = key.trim();

  if (trimmed.length <= HTTP_IDEMPOTENCY_KEY_MAX_LEN) {
    return trimmed;
  }

  return trimmed.slice(0, HTTP_IDEMPOTENCY_KEY_MAX_LEN);
}

/**
 * Headers for idempotent writes. Always includes `Idempotency-Key`.
 */
export function idempotencyRequestHeaders(idempotencyKey?: string | null): Record<string, string> {
  const resolved =
    idempotencyKey != null && idempotencyKey.trim() !== ''
      ? normalizeIdempotencyKey(idempotencyKey)
      : buildHttpIdempotencyKey();

  return { [HTTP_IDEMPOTENCY_KEY_HEADER]: resolved };
}

/**
 * Merges optional If-Match (optimistic concurrency) and Idempotency-Key headers.
 */
export function adminMutationRequestHeaders(
  options?:
    | AdminHttpMutationOptions
    | Pick<AdminConfigMutationOptions, 'ifMatch' | 'idempotencyKey'>
): Record<string, string> | undefined {
  const ifMatch = options != null && 'ifMatch' in options ? options.ifMatch : undefined;

  const idempotencyKey =
    options != null && 'idempotencyKey' in options ? options.idempotencyKey : undefined;

  return mergeRequestHeaders(
    ifMatchRequestHeaders(ifMatch),
    idempotencyRequestHeaders(idempotencyKey)
  );
}

/**
 * Headers for admin config writes: always optional If-Match; Idempotency-Key only when opted in.
 */
export function adminConfigWriteHeaders(
  options?: AdminConfigMutationOptions
): Record<string, string> | undefined {
  const idem = options?.sendIdempotency
    ? idempotencyRequestHeaders(options.idempotencyKey)
    : undefined;

  return mergeRequestHeaders(ifMatchRequestHeaders(options?.ifMatch), idem);
}

export function readIdempotentReplayedFromResponse(response: Response): boolean {
  const raw = response.headers.get(HTTP_HEADER_IDEMPOTENT_REPLAYED)?.trim().toLowerCase();

  return raw === HTTP_HEADER_IDEMPOTENT_REPLAYED_VALUE_TRUE;
}
