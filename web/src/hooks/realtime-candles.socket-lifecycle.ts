/**
 * Binance kline WebSocket lifecycle (non-React) — used by useRealtimeCandles.
 */

import type { Dispatch, MutableRefObject, SetStateAction } from 'react';

import { buildConnectingState, type WebSocketState } from '@/hooks/realtime-candles.internals';
import { openBinanceKlineWebSocket } from '@/hooks/realtime-candles.socket-handlers';
import type { Timeframe } from '@/types/chart';
import { shouldDeferWebSocketConnectForPageVisibility } from '@/utils/page-visibility-session';
import { subscribeSocketVisibilityPause } from '@/utils/socket-visibility-pause';

type RealtimeCandlesSocketRefs = {
  wsRef: MutableRefObject<WebSocket | null>;
  reconnectAttemptsRef: MutableRefObject<number>;
  reconnectTimeoutRef: MutableRefObject<ReturnType<typeof setTimeout> | null>;
  connectionKeyRef: MutableRefObject<string>;
  pausedByVisibilityRef: MutableRefObject<boolean>;
  lastKlineLogRef: MutableRefObject<{ k_t_ms: number; k_x: boolean } | null>;
  lastEventTimeRef: MutableRefObject<number>;
};

/**
 * Tear down a kline socket without "closed before connection established" noise.
 * React Strict Mode runs effect cleanup while the socket is still CONNECTING.
 */
export function closeWebSocketSafely(wsRef: MutableRefObject<WebSocket | null>): void {
  const ws = wsRef.current;

  if (ws == null) {
    return;
  }

  ws.onopen = null;
  ws.onmessage = null;
  ws.onclose = null;
  ws.onerror = null;

  if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) {
    ws.close();
  }

  wsRef.current = null;
}

export type RunRealtimeCandlesSocketEffectParams = {
  symbol: string;
  timeframe: Timeframe;
  connectionKey: string;
  refs: RealtimeCandlesSocketRefs;
  /** Immediate setter for lifecycle (open/close) transitions. */
  setState: Dispatch<SetStateAction<WebSocketState>>;
  /** Frame-coalesced setter for the high-frequency kline tick only. */
  dispatchTick: Dispatch<SetStateAction<WebSocketState>>;
};

export function runRealtimeCandlesSocketEffect({
  symbol,
  timeframe,
  connectionKey,
  refs,
  setState,
  dispatchTick,
}: RunRealtimeCandlesSocketEffectParams): () => void {
  refs.connectionKeyRef.current = connectionKey;

  let isCleanedUp = false;
  let isInitialConnect = true;

  const isCleanedUpFn = (): boolean => isCleanedUp;

  const clearReconnectTimeout = (): void => {
    if (refs.reconnectTimeoutRef.current) {
      clearTimeout(refs.reconnectTimeoutRef.current);
      refs.reconnectTimeoutRef.current = null;
    }
  };

  const closeSocket = (): void => {
    closeWebSocketSafely(refs.wsRef);
  };

  const cleanup = (): void => {
    isCleanedUp = true;
    clearReconnectTimeout();
    closeSocket();
  };

  const pauseForVisibility = (): void => {
    refs.pausedByVisibilityRef.current = true;
    clearReconnectTimeout();
    closeSocket();
  };

  const connect = (): void => {
    if (
      isCleanedUp ||
      shouldDeferWebSocketConnectForPageVisibility(refs.pausedByVisibilityRef.current)
    ) {
      return;
    }

    closeSocket();

    if (isInitialConnect) {
      setState(buildConnectingState(timeframe));
      isInitialConnect = false;
    }

    openBinanceKlineWebSocket(symbol, timeframe, {
      connectionKey,
      isCleanedUp: isCleanedUpFn,
      connectionKeyRef: refs.connectionKeyRef,
      pausedByVisibilityRef: refs.pausedByVisibilityRef,
      reconnectAttemptsRef: refs.reconnectAttemptsRef,
      reconnectTimeoutRef: refs.reconnectTimeoutRef,
      lastKlineLogRef: refs.lastKlineLogRef,
      lastEventTimeRef: refs.lastEventTimeRef,
      wsRef: refs.wsRef,
      setState,
      dispatchTick,
      scheduleReconnect: connect,
    });
  };

  connect();

  const unsubscribeVisibility = subscribeSocketVisibilityPause({
    pausedByVisibilityRef: refs.pausedByVisibilityRef,
    reconnectAttemptsRef: refs.reconnectAttemptsRef,
    pause: pauseForVisibility,
    reconnect: connect,
  });

  return () => {
    unsubscribeVisibility();
    cleanup();
  };
}
