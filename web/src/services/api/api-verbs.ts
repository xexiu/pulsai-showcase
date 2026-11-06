import { authenticatedFetch } from '@/services/api/api-authenticated-fetch';

/**
 * Helper to make authenticated GET requests.
 */
export async function authenticatedGet(url: string, signal?: AbortSignal): Promise<Response> {
  const init: RequestInit = { method: 'GET' };

  if (signal) {
    init.signal = signal;
  }

  return authenticatedFetch(url, init);
}

/**
 * Helper to make authenticated POST requests with JSON body.
 */
export async function authenticatedPost(
  url: string,
  body: unknown,
  signal?: AbortSignal
): Promise<Response> {
  const init: RequestInit = {
    method: 'POST',
    body: JSON.stringify(body),
  };

  if (signal) {
    init.signal = signal;
  }

  return authenticatedFetch(url, init);
}

/**
 * Helper to make authenticated PUT requests with JSON body.
 */
export async function authenticatedPut(
  url: string,
  body: unknown,
  signal?: AbortSignal
): Promise<Response> {
  const init: RequestInit = {
    method: 'PUT',
    body: JSON.stringify(body),
  };

  if (signal) {
    init.signal = signal;
  }

  return authenticatedFetch(url, init);
}

/**
 * Helper to make authenticated DELETE requests.
 */
export async function authenticatedDelete(url: string, signal?: AbortSignal): Promise<Response> {
  const init: RequestInit = { method: 'DELETE' };

  if (signal) {
    init.signal = signal;
  }

  return authenticatedFetch(url, init);
}
