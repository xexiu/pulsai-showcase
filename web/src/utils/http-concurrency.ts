/**
 * HTTP optimistic concurrency (ETag / If-Match) — FE SoT aligned with BE `http_concurrency.py`.
 */

export const HTTP_STATUS_PRECONDITION_FAILED = 412;

const STALE_RESOURCE_ERROR_NAME = 'StaleResourceError';

/** Thrown when the server returns 412 (stale If-Match). Caller should refetch and notify the user. */
export class StaleResourceError extends Error {
  constructor(message = 'Resource was modified elsewhere') {
    super(message);
    this.name = STALE_RESOURCE_ERROR_NAME;
  }
}

export function isStaleResourceError(error: unknown): error is StaleResourceError {
  return error instanceof StaleResourceError;
}

/**
 * Read strong ETag from a fetch Response (header names are case-insensitive).
 */
export function readEtagFromResponse(response: Response): string | null {
  const raw = response.headers.get('etag');

  if (raw == null) {
    return null;
  }
  const trimmed = raw.trim();

  return trimmed.length > 0 ? trimmed : null;
}

/**
 * Headers for conditional writes. Omit header when etag is unknown (BE allows write).
 */
export function ifMatchRequestHeaders(ifMatch: string | null | undefined): HeadersInit | undefined {
  if (ifMatch == null || ifMatch.trim() === '') {
    return undefined;
  }

  return { 'If-Match': ifMatch.trim() };
}

export function assertResponseNotStale(response: Response): void {
  if (response.status === HTTP_STATUS_PRECONDITION_FAILED) {
    throw new StaleResourceError();
  }
}
