/**
 * Binance kline WebSocket event handlers — used by realtime-candles.socket-lifecycle.
 */

import type { Dispatch, MutableRefObject, SetStateAction } from 'react';

import {
  buildConnectedFromPrevious,
  buildDisconnectedState,
  buildReconnectingState,
  buildWebSocketUrl,
  MAX_RECONNECT_ATTEMPTS,
  parseKlineEvent,
  RECONNECT_DELAY_MS,
  rememberHealthyConnection,
  type BinanceKlineEvent,
  type WebSocketState,
} from '@/hooks/realtime-candles.internals';
import type { Timeframe } from '@/types/chart';
import { chartLiveTrace } from '@/utils/chart-live-investigate';

export type AttachBinanceKlineHandlersParams = {
  ws: WebSocket;
  symbol: string;
  timeframe: Timeframe;
  connectionKey: string;
  isCleanedUp: () => boolean;
  connectionKeyRef: MutableRefObject<string>;
  pausedByVisibilityRef: MutableRefObject<boolean>;
  reconnectAttemptsRef: MutableRefObject<number>;
  reconnectTimeoutRef: MutableRefObject<ReturnType<typeof setTimeout> | null>;
  lastKlineLogRef: MutableRefObject<{ k_t_ms: number; k_x: boolean } | null>;
  /** Last applied Binance event time (ms); drops stale / out-of-order frames. */
  lastEventTimeRef: MutableRefObject<number>;
  wsRef: MutableRefObject<WebSocket | null>;
  /** Immediate setter for lifecycle (open/close) transitions. */
  setState: Dispatch<SetStateAction<WebSocketState>>;
  /** Frame-coalesced setter for the high-frequency kline tick only. */
  dispatchTick: Dispatch<SetStateAction<WebSocketState>>;
  scheduleReconnect: () => void;
};

function attachBinanceKlineWebSocketHandlers(params: AttachBinanceKlineHandlersParams): void {
  const {
    ws,
    symbol,
    timeframe,
    connectionKey,
    isCleanedUp,
    connectionKeyRef,
    pausedByVisibilityRef,
    reconnectAttemptsRef,
    reconnectTimeoutRef,
    lastKlineLogRef,
    lastEventTimeRef,
    wsRef,
    setState,
    dispatchTick,
    scheduleReconnect,
  } = params;

  const currentKey = connectionKey;

  ws.onopen = () => {
    if (isCleanedUp() || connectionKeyRef.current !== currentKey) return;
    rememberHealthyConnection();
    setState((prev) => ({
      ...buildConnectedFromPrevious(prev),
      klineStreamTimeframe: timeframe,
    }));
    reconnectAttemptsRef.current = 0;
  };

  ws.onmessage = (event) => {
    if (isCleanedUp() || connectionKeyRef.current !== currentKey) return;

    try {
      const data = JSON.parse(event.data as string) as BinanceKlineEvent;

      if (data.e === 'kline' && data.k) {
        // Drop-stale: ignore frames older than the last applied event time. Binance `E`
        // is monotonic server time, so this silently discards out-of-order / replayed
        // ticks (e.g. a reconnect burst) that would briefly render a stale price.
        const eventTimeMs = typeof data.E === 'number' ? data.E : null;

        if (eventTimeMs !== null && eventTimeMs <= lastEventTimeRef.current) {
          return;
        }

        if (eventTimeMs !== null) {
          lastEventTimeRef.current = eventTimeMs;
        }

        const barOpenSec =
          typeof data.k.t === 'number' && Number.isFinite(data.k.t)
            ? Math.floor(data.k.t / 1000)
            : null;
        const prev = lastKlineLogRef.current;
        const changed = prev === null || prev.k_t_ms !== data.k.t || prev.k_x !== data.k.x;

        if (changed) {
          lastKlineLogRef.current = { k_t_ms: data.k.t, k_x: data.k.x };
          chartLiveTrace('binance-kline.tick', {
            symbol,
            timeframe,
            barOpenSec,
            isClosed: data.k.x,
            close: data.k.c,
          });
        }

        const candle = parseKlineEvent(data);
        const now = Date.now();

        rememberHealthyConnection(now);

        // Coalesced onto the next frame (dispatchTick) — the only high-frequency setter.
        dispatchTick((prev) => ({
          ...prev,
          badgeState: 'connected',
          liveCandle: candle ?? null,
          klineStreamTimeframe: timeframe,
          lastUpdate: now,
          isCandleClosed: data.k.x,
          lastBarCloseOpenTimeSec:
            data.k.x && barOpenSec != null ? barOpenSec : prev.lastBarCloseOpenTimeSec,
        }));
      }
    } catch {
      // Ignore parse errors (ping/pong frames)
    }
  };

  ws.onclose = () => {
    if (isCleanedUp() || connectionKeyRef.current !== currentKey) return;
    if (pausedByVisibilityRef.current) return;

    if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
      const delay = RECONNECT_DELAY_MS * Math.pow(2, reconnectAttemptsRef.current);

      setState((prev) => buildReconnectingState(prev));
      reconnectAttemptsRef.current += 1;
      reconnectTimeoutRef.current = setTimeout(scheduleReconnect, delay);

      return;
    }

    setState(buildDisconnectedState());
  };

  ws.onerror = () => {
    if (!isCleanedUp() && connectionKeyRef.current === currentKey) {
      // Expected during symbol switches; onclose handles reconnect.
    }
  };

  wsRef.current = ws;
}

export function openBinanceKlineWebSocket(
  symbol: string,
  timeframe: Timeframe,
  handlerParams: Omit<AttachBinanceKlineHandlersParams, 'ws' | 'symbol' | 'timeframe'>
): WebSocket {
  const ws = new WebSocket(buildWebSocketUrl(symbol, timeframe));

  attachBinanceKlineWebSocketHandlers({
    ws,
    symbol,
    timeframe,
    ...handlerParams,
  });

  return ws;
}
