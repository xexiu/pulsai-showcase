/**
 * Parse error body from API responses (FastAPI-style and PulsAI middleware).
 *
 * SoT for turning response.json() into a user-facing message:
 * - error.message (PulsAI middleware) → use as-is (e.g. "body: model_version required...")
 * - detail as string → use as-is
 * - detail as array (validation) → first item msg
 * - 5xx / parse failure → friendly fallback
 *
 * @see docs/04-structural/CODING_STANDARDS.md §2 NO-DRY
 */

/** PulsAI middleware validation error prefix to strip for cleaner UI. */
const ERROR_BODY_PREFIX = 'body: ';

/** FastAPI error body: detail can be string or array of validation errors. */
interface ApiErrorBody {
  detail?: string | Array<{ msg?: string; loc?: unknown }>;
  message?: string;
  error?: { message?: string; details?: { errors?: Array<{ msg?: string }> } };
}

function getMessageFromErrorObject(err: ApiErrorBody['error']): string | null {
  if (err == null) {
    return null;
  }
  if (typeof err.message === 'string' && err.message.length > 0) {
    const msg = err.message;

    return msg.startsWith(ERROR_BODY_PREFIX) ? msg.slice(ERROR_BODY_PREFIX.length).trim() : msg;
  }

  const details = err.details as { errors?: Array<{ msg?: string }> } | undefined;
  const first = details?.errors?.[0]?.msg;

  return typeof first === 'string' && first.length > 0 ? first : null;
}

function getMessageFromDetailOrMessage(body: ApiErrorBody): string | null {
  if (typeof body.detail === 'string' && body.detail.length > 0) {
    return body.detail;
  }
  /** Some legacy/admin responses use `detail: { message: "..." }` instead of a string. */
  if (typeof body.detail === 'object' && body.detail !== null && !Array.isArray(body.detail)) {
    const nested = (body.detail as { message?: string }).message;

    if (typeof nested === 'string' && nested.length > 0) {
      return nested;
    }
  }
  if (Array.isArray(body.detail) && body.detail.length > 0) {
    const first = body.detail[0];

    if (first && typeof first === 'object' && typeof (first as { msg?: string }).msg === 'string') {
      return (first as { msg: string }).msg;
    }
  }
  if (typeof body.message === 'string' && body.message.length > 0) {
    return body.message;
  }

  return null;
}

/**
 * Extract a single user-facing message from an API error response body.
 * Supports both raw FastAPI (detail) and PulsAI middleware (error.message) shapes.
 *
 * @param errorData - Parsed JSON from response.json().catch(...)
 * @param fallback - Message when no usable message found
 * @returns Message to show in UI (friendly, no stack traces)
 */
export function parseApiErrorDetail(errorData: unknown, fallback: string): string {
  if (errorData == null || typeof errorData !== 'object') {
    return fallback;
  }

  const body = errorData as ApiErrorBody;
  const fromError = getMessageFromErrorObject(body.error);

  if (fromError != null) {
    return fromError;
  }

  const fromDetail = getMessageFromDetailOrMessage(body);

  if (fromDetail != null) {
    return fromDetail;
  }

  return fallback;
}

/**
 * Throw a user-facing `Error` when {@link Response.ok} is false; resolve silently otherwise.
 *
 * Wraps the canonical fetcher tail used across `apps/web/src/config/queryFetchers*.ts`:
 *
 * ```ts
 * if (!response.ok) {
 *   const data = await response.json().catch(() => ({}));
 *   const message = parseApiErrorDetail(data, `<context>: ${response.status}`);
 *   throw new Error(message);
 * }
 * ```
 *
 * Body parsing failures (non-JSON, empty body) fall through to `"<fallbackContext>: <status>"`.
 *
 * @param response - The fetch response to assert on.
 * @param fallbackContext - Human-readable label appended with `: <status>` when no body message exists.
 *
 * @see docs/04-structural/CODING_STANDARDS.md §2 NO-DRY
 */
export async function throwIfNotOk(response: Response, fallbackContext: string): Promise<void> {
  if (response.ok) {
    return;
  }

  const data: unknown = await response.json().catch(() => ({}));
  const message = parseApiErrorDetail(data, `${fallbackContext}: ${response.status}`);

  throw new Error(message);
}
