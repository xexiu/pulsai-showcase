/**
 * Binance WebSocket kline helpers + connection grace memory (non-React).
 *
 * WHY separate from useRealtimeCandles.ts?
 * - Facade hook focuses on effects + lifecycle; pure logic is testable in isolation.
 * - Module-level `realtimeConnectionMemory` stays here (single process singleton).
 */

import type {
  BinanceKlineEvent,
  RealtimeCandlesBadgeState,
  RealtimeCandlesConnectionState,
  WebSocketState,
} from '@/hooks/realtime-candles.types';
import type { CandlestickData, Timeframe } from '@/types/chart';
import { POLL_INTERVALS } from '@/utils/constants';

export type {
  BinanceKlineEvent,
  RealtimeCandlesBadgeState,
  RealtimeCandlesConnectionState,
  UseRealtimeCandlesResult,
  WebSocketState,
} from '@/hooks/realtime-candles.types';

/**
 * Public Binance stream (browser WebSocket).
 * @see apps/web/next.config.mjs `CSP_EXTRA_CONNECT_ORIGINS` — changing host/port requires CSP update.
 */
const BINANCE_WS_BASE = 'wss://stream.binance.com:9443/ws';

export const RECONNECT_DELAY_MS = POLL_INTERVALS.RECONNECT;

const OFFLINE_GRACE_MS = 3000;

export const MAX_RECONNECT_ATTEMPTS = 5;

const realtimeConnectionMemory = {
  lastHealthyAt: null as number | null,
};

export const DISCONNECTED_STATE: WebSocketState = {
  liveCandle: null,
  klineStreamTimeframe: null,
  connectionState: 'disconnected',
  badgeState: 'disconnected',
  isConnected: false,
  lastUpdate: null,
  isCandleClosed: false,
  lastBarCloseOpenTimeSec: null,
};

export function hasRecentHealthyConnection(now: number = Date.now()): boolean {
  if (realtimeConnectionMemory.lastHealthyAt == null) {
    return false;
  }

  return now - realtimeConnectionMemory.lastHealthyAt < OFFLINE_GRACE_MS;
}

export function getOfflineGraceRemainingMs(now: number = Date.now()): number {
  if (realtimeConnectionMemory.lastHealthyAt == null) {
    return 0;
  }

  const elapsedMs = now - realtimeConnectionMemory.lastHealthyAt;

  return Math.max(OFFLINE_GRACE_MS - elapsedMs, 0);
}

export function rememberHealthyConnection(now: number = Date.now()): void {
  realtimeConnectionMemory.lastHealthyAt = now;
}

/** @internal Test-only reset for module-level WS health memory. */
export function resetRealtimeConnectionMemoryForTests(): void {
  realtimeConnectionMemory.lastHealthyAt = null;
}

function buildSocketState(
  connectionState: RealtimeCandlesConnectionState,
  badgeState: RealtimeCandlesBadgeState
): WebSocketState {
  return {
    liveCandle: null,
    klineStreamTimeframe: null,
    connectionState,
    badgeState,
    isConnected: connectionState === 'connected',
    lastUpdate: null,
    isCandleClosed: false,
    lastBarCloseOpenTimeSec: null,
  };
}

/**
 * Connecting state for a new symbol/TF socket only (not on reconnect).
 * Do not hydrate a stale cached candle — that caused wrong bars after hard refresh.
 */
export function buildConnectingState(timeframe?: Timeframe): WebSocketState {
  return {
    ...buildSocketState('connecting', hasRecentHealthyConnection() ? 'connected' : 'disconnected'),
    ...(timeframe != null ? { klineStreamTimeframe: timeframe } : {}),
  };
}

/** Preserve last candle while the Binance socket reconnects (avoids LiveChartGate loading flash). */
export function buildReconnectingState(previous: WebSocketState): WebSocketState {
  const keepLiveBadge = previous.liveCandle != null || hasRecentHealthyConnection();

  return {
    ...previous,
    connectionState: 'connecting',
    badgeState: keepLiveBadge ? 'connected' : 'disconnected',
    isConnected: false,
  };
}

/** Preserve the last live candle when the Binance socket re-opens (avoids chartReady flicker). */
export function buildConnectedFromPrevious(previous: WebSocketState): WebSocketState {
  return {
    ...previous,
    connectionState: 'connected',
    badgeState: 'connected',
    isConnected: true,
  };
}

export function buildDisconnectedState(): WebSocketState {
  return buildSocketState(
    'disconnected',
    hasRecentHealthyConnection() ? 'connected' : 'disconnected'
  );
}

export function formatSymbolForBinance(symbol: string): string {
  return symbol.replace('/', '').toLowerCase();
}

export function buildWebSocketUrl(symbol: string, timeframe: Timeframe): string {
  return `${BINANCE_WS_BASE}/${formatSymbolForBinance(symbol)}@kline_${timeframe}`;
}

export function parseKlineEvent(event: BinanceKlineEvent): CandlestickData | null {
  const { k } = event;
  const t = typeof k.t === 'number' && Number.isFinite(k.t) ? Math.floor(k.t / 1000) : Number.NaN;

  if (!Number.isFinite(t) || t <= 0) return null;

  return {
    time: t,
    open: parseFloat(k.o),
    high: parseFloat(k.h),
    low: parseFloat(k.l),
    close: parseFloat(k.c),
  };
}
