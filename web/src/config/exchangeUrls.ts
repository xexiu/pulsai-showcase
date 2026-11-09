/**
 * HTTP URL builders for `/api/v1/exchanges/*` (supported catalog, connections, leverage tiers).
 *
 * SoT for paths consumed by `queryFetchersExchangeConnections.ts`.
 */

import { EXCHANGES_ENDPOINT } from '@/config/api';

export function buildExchangesSupportedUrl(): string {
  return `${EXCHANGES_ENDPOINT}/supported`;
}

/** GET authenticated list of the user's exchange connections (`EXCHANGES_ENDPOINT` base). */
export function buildExchangesConnectionsListUrl(): string {
  return EXCHANGES_ENDPOINT;
}

export function buildExchangeConnectUrl(): string {
  return `${EXCHANGES_ENDPOINT}/connect`;
}

export function buildExchangeConnectionUrl(connectionId: string): string {
  return `${EXCHANGES_ENDPOINT}/${encodeURIComponent(connectionId)}`;
}

export function buildExchangeVerifyUrl(connectionId: string): string {
  return `${EXCHANGES_ENDPOINT}/${encodeURIComponent(connectionId)}/verify`;
}

export function buildExchangeLeverageTiersUrl(connectionId: string, symbol: string): string {
  const params = new URLSearchParams({ symbol });

  return `${EXCHANGES_ENDPOINT}/${encodeURIComponent(connectionId)}/leverage-tiers?${params.toString()}`;
}
