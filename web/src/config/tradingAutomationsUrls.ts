/**
 * HTTP URL builders for GET/PATCH/POST under `/api/v1/trading/automations/*`.
 *
 * SoT for path segments consumed by `queryFetchersTradingAutomations.ts` (§5.4 fetchers).
 */

import { TRADING_ENDPOINT } from '@/config/api';

const TRADING_AUTOMATIONS_SEGMENT = 'automations' as const;

function tradingAutomationsBaseUrl(): string {
  return `${TRADING_ENDPOINT}/${TRADING_AUTOMATIONS_SEGMENT}`;
}

export function buildTradingAutomationsListUrl(limit: number, offset: number): string {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  return `${tradingAutomationsBaseUrl()}?${params.toString()}`;
}

export function buildTradingAutomationsEligibilityUrl(): string {
  return `${tradingAutomationsBaseUrl()}/eligibility`;
}

export function buildTradingAutomationsActiveUrl(): string {
  return `${tradingAutomationsBaseUrl()}/active`;
}

export function buildTradingAutomationByIdUrl(automationId: string): string {
  return `${tradingAutomationsBaseUrl()}/${encodeURIComponent(automationId)}`;
}

export function buildTradingAutomationSelectAsActiveUrl(automationId: string): string {
  return `${tradingAutomationsBaseUrl()}/${encodeURIComponent(automationId)}/select-as-active`;
}

export function buildTradingAutomationPromoteFromBacktestUrl(): string {
  return `${tradingAutomationsBaseUrl()}/promote-from-backtest`;
}

export function buildTradingAutomationPromoteFromPublicBacktestUrl(): string {
  return `${tradingAutomationsBaseUrl()}/promote-from-public-backtest`;
}
