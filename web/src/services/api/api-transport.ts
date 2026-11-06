import { API_BASE_URL, resolveEventStreamUrl } from '@/config/api';

export { resolveEventStreamUrl };

export async function fetchWithCredentials(
  resolvedUrl: string,
  options: RequestInit | undefined,
  headers: Headers
): Promise<Response> {
  const requestInit: RequestInit = {
    ...options,
    headers,
    credentials: 'include',
  };
  const response = await fetch(resolvedUrl, requestInit);

  if (!shouldFallbackToDirectApi(resolvedUrl, response.status)) {
    return response;
  }

  return fetch(toDirectApiUrl(resolvedUrl), requestInit);
}

export function shouldFallbackToDirectApi(url: string, status: number): boolean {
  const isProxyApiCall = url.startsWith('/api/v1/');

  if (!isProxyApiCall) {
    return false;
  }

  // Next.js proxy can transiently fail with 5xx during backend reloads.
  return status >= 500;
}

export function toDirectApiUrl(url: string): string {
  if (!url.startsWith('/')) {
    return url;
  }

  return `${API_BASE_URL}${url}`;
}
