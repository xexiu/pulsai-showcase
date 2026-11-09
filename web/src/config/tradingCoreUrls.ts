/**
 * HTTP URL builders for GET/POST under `${TRADING_ENDPOINT}/*` (modes, portfolio, orders, etc.).
 *
 * SoT for paths consumed by `queryFetchersTradingCore.ts` (§5.4 fetchers, §12 API paths).
 */

import { DEMO_ENDPOINT, TRADING_ENDPOINT } from '@/config/api';
import { TRADING_ACTIVITY_FETCH_LIMIT, type TradingModeKind } from '@/utils/constants/trading';

/** Wire keys for GET ``/trading/performance/*`` window query string (matches BE param names). */
const TRADING_PERFORMANCE_QUERY = {
  START_DATE: 'start_date',
  END_DATE: 'end_date',
  MODE: 'mode',
  EXCHANGE_CONNECTION_ID: 'exchange_connection_id',
  SYMBOL: 'symbol',
} as const;

function buildTradingPerformanceWindowSearchParams(params: {
  startDate: string;
  endDate: string;
  mode: TradingModeKind;
  exchangeConnectionId?: string | null;
  symbol?: string | null;
}): URLSearchParams {
  const search = new URLSearchParams({
    [TRADING_PERFORMANCE_QUERY.START_DATE]: params.startDate,
    [TRADING_PERFORMANCE_QUERY.END_DATE]: params.endDate,
    [TRADING_PERFORMANCE_QUERY.MODE]: params.mode,
  });

  if (params.exchangeConnectionId) {
    search.set(TRADING_PERFORMANCE_QUERY.EXCHANGE_CONNECTION_ID, params.exchangeConnectionId);
  }

  if (params.symbol) {
    search.set(TRADING_PERFORMANCE_QUERY.SYMBOL, params.symbol);
  }

  return search;
}

export function buildTradingModesUrl(): string {
  return `${TRADING_ENDPOINT}/modes`;
}

export function buildTradingModeSelectionUrl(): string {
  return `${TRADING_ENDPOINT}/mode-selection`;
}

export function buildTradingPerformanceDailyUrl(params: {
  startDate: string;
  endDate: string;
  mode: TradingModeKind;
  exchangeConnectionId?: string | null;
}): string {
  const search = buildTradingPerformanceWindowSearchParams({
    ...params,
    symbol: null,
  });

  return `${TRADING_ENDPOINT}/performance/daily?${search.toString()}`;
}

/**
 * GET ``/trading/performance/summary`` — window-scalar KPI summary for the
 * in-page Estadísticas tab. Co-located under the same `performance/` namespace
 * as `/performance/daily` for discoverability; returns a different read-model
 * shape (scalars vs. time series) per SRP.
 */
export function buildTradingPerformanceSummaryUrl(params: {
  startDate: string;
  endDate: string;
  mode: TradingModeKind;
  exchangeConnectionId?: string | null;
  /** Optional product filter (paper); demo/live may ignore. */
  symbol?: string | null;
}): string {
  const search = buildTradingPerformanceWindowSearchParams(params);

  return `${TRADING_ENDPOINT}/performance/summary?${search.toString()}`;
}

/**
 * GET ``/trading/performance/equity-series`` — daily UTC cumulative realized
 * P&L for the in-page Estadísticas tab (sibling of `/performance/summary`).
 * Optional `symbol` partitions the paper series by product (demo ignores).
 */
export function buildTradingEquitySeriesUrl(params: {
  startDate: string;
  endDate: string;
  mode: TradingModeKind;
  exchangeConnectionId?: string | null;
  symbol?: string | null;
}): string {
  const search = buildTradingPerformanceWindowSearchParams(params);

  return `${TRADING_ENDPOINT}/performance/equity-series?${search.toString()}`;
}

/**
 * Demo trade/order URL builders.
 *
 * Epic B (RefactorHuge): these endpoints moved from ``/trading/*`` to ``/demo/*``
 * — only demo persists BE-side; paper/live order routes are gone (FE live-direct
 * via HMAC). The ``mode`` argument is kept for caller-symmetry but no longer
 * sent on the wire (BE hardcodes ``mode="demo"``).
 */
export function buildTradingPortfolioUrl(
  _mode: TradingModeKind,
  exchangeConnectionId?: string | null
): string {
  const params = new URLSearchParams();

  if (exchangeConnectionId) {
    params.set('exchange_connection_id', exchangeConnectionId);
  }

  const qs = params.toString();

  return qs ? `${DEMO_ENDPOINT}/portfolio?${qs}` : `${DEMO_ENDPOINT}/portfolio`;
}

export function buildTradingTradesUrl(
  _mode: TradingModeKind,
  exchangeConnectionId?: string | null,
  tradeDate?: string | null
): string {
  const params = new URLSearchParams({
    limit: String(TRADING_ACTIVITY_FETCH_LIMIT),
  });

  if (exchangeConnectionId) {
    params.set('exchange_connection_id', exchangeConnectionId);
  }

  if (tradeDate) {
    params.set('trade_date', tradeDate);
  }

  return `${DEMO_ENDPOINT}/trades?${params.toString()}`;
}

export function buildTradingOrdersListUrl(
  _mode: TradingModeKind,
  exchangeConnectionId?: string | null
): string {
  const params = new URLSearchParams({
    limit: String(TRADING_ACTIVITY_FETCH_LIMIT),
  });

  if (exchangeConnectionId) {
    params.set('exchange_connection_id', exchangeConnectionId);
  }

  return `${DEMO_ENDPOINT}/orders?${params.toString()}`;
}

export function buildTradingOrdersCancelUrl(): string {
  return `${DEMO_ENDPOINT}/orders/cancel`;
}

export function buildTradingOrdersPlaceUrl(): string {
  return `${DEMO_ENDPOINT}/orders`;
}

export function buildTradingResetUrl(): string {
  return `${DEMO_ENDPOINT}/reset`;
}
