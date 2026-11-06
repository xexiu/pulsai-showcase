/**
 * Pause a live socket while the page is hidden; reconnect it from a clean backoff when it returns.
 *
 * IMPORTERS/CALLERS: `@/hooks/use-signals-websocket.lifecycle`, `@/hooks/realtime-candles.socket-lifecycle`.
 * AFFECTED API: none -- the two sockets already wired exactly this, line for line.
 * DATA SCHEMAS: none.
 *
 * One home for what both sockets did by copy (the duplicate-lines gate measured 11 identical lines).
 * Kept OUT of `page-visibility-session` on purpose: tests spy on that module's export, and a call from
 * inside the same module would bypass the spy.
 */

import { subscribePageVisibilityWebSocketPause } from '@/utils/page-visibility-session';

export type SocketVisibilityPauseParams = {
  pausedByVisibilityRef: { current: boolean };
  reconnectAttemptsRef: { current: number };
  /** Close the socket for the hidden period. */
  pause: () => void;
  /** Open it again; called after the backoff counter is reset. */
  reconnect: () => void;
};

/** Returns the unsubscribe function, like the subscription it wraps. */
export function subscribeSocketVisibilityPause(params: SocketVisibilityPauseParams): () => void {
  return subscribePageVisibilityWebSocketPause({
    isPausedByVisibility: () => params.pausedByVisibilityRef.current,
    setPausedByVisibility: (paused) => {
      params.pausedByVisibilityRef.current = paused;
    },
    onVisibilityPause: params.pause,
    onVisibilityResume: () => {
      params.reconnectAttemptsRef.current = 0;
      params.reconnect();
    },
  });
}
