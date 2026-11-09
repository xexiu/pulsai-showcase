/**
 * Shared GET/PATCH/PUT/DELETE helpers for admin JSON configs with ETag / If-Match.
 */

import { appFetch } from '@/services/api';
import type {
  AdminConfigMutationOptions,
  AdminConfigWithEtag,
} from '@/types/admin-config-with-etag';
import { assertResponseNotStale, readEtagFromResponse } from '@/utils/http-concurrency';
import { adminConfigWriteHeaders } from '@/utils/http-idempotency';
import { parseApiErrorDetail } from '@/utils/parseApiErrorBody';

export async function fetchAdminConfigJson<T>(
  url: string,
  signal?: AbortSignal,
  errorMessage = 'Failed to fetch config'
): Promise<AdminConfigWithEtag<T>> {
  const response = await appFetch({ signal, url, auth: true });

  if (!response.ok) {
    throw new Error(`${errorMessage}: ${response.status}`);
  }

  const data = (await response.json()) as T;

  return { data, etag: readEtagFromResponse(response) };
}

export async function patchAdminConfigJson<TBody, TResponse>(
  url: string,
  body: TBody,
  options: AdminConfigMutationOptions | undefined,
  errorMessage: string
): Promise<AdminConfigWithEtag<TResponse>> {
  const headers = adminConfigWriteHeaders(options);
  const response = await appFetch({
    signal: options?.signal,
    url,
    auth: true,
    method: 'PATCH',
    body: JSON.stringify(body),
    ...(headers ? { headers } : {}),
  });

  assertResponseNotStale(response);

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));

    throw new Error(parseApiErrorDetail(data, `${errorMessage}: ${response.status}`));
  }

  const data = (await response.json()) as TResponse;

  return { data, etag: readEtagFromResponse(response) };
}

export async function putAdminConfigJson<TBody, TResponse>(
  url: string,
  body: TBody,
  options: AdminConfigMutationOptions | undefined,
  errorMessage: string
): Promise<AdminConfigWithEtag<TResponse>> {
  const headers = adminConfigWriteHeaders(options);
  const response = await appFetch({
    signal: options?.signal,
    url,
    auth: true,
    method: 'PUT',
    body: JSON.stringify(body),
    ...(headers ? { headers } : {}),
  });

  assertResponseNotStale(response);

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));

    throw new Error(parseApiErrorDetail(data, `${errorMessage}: ${response.status}`));
  }

  const data = (await response.json()) as TResponse;

  return { data, etag: readEtagFromResponse(response) };
}

export async function deleteAdminConfigJson<TResponse>(
  url: string,
  options: AdminConfigMutationOptions | undefined,
  errorMessage: string
): Promise<AdminConfigWithEtag<TResponse>> {
  const headers = adminConfigWriteHeaders(options);
  const response = await appFetch({
    signal: options?.signal,
    url,
    auth: true,
    method: 'DELETE',
    ...(headers ? { headers } : {}),
  });

  assertResponseNotStale(response);

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));

    throw new Error(parseApiErrorDetail(data, `${errorMessage}: ${response.status}`));
  }

  const data = (await response.json()) as TResponse;

  return { data, etag: readEtagFromResponse(response) };
}
