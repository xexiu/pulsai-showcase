/**
 * @see apps/web/src/hooks/realtime-candles.socket-lifecycle.ts
 */

import { describe, expect, it, vi } from 'vitest';

import { closeWebSocketSafely } from '@/hooks/realtime-candles.socket-lifecycle';

describe('closeWebSocketSafely', () => {
  it('defers close until open when socket is still CONNECTING (Strict Mode cleanup)', () => {
    const close = vi.fn();
    const ws = {
      readyState: WebSocket.CONNECTING,
      onopen: null as (() => void) | null,
      onmessage: null,
      onclose: null,
      onerror: null,
      close,
      addEventListener: vi.fn((type: string, listener: () => void) => {
        if (type === 'open') {
          listener();
        }
      }),
    } as unknown as WebSocket;

    const wsRef = { current: ws };

    closeWebSocketSafely(wsRef);

    expect(wsRef.current).toBeNull();
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('closes immediately when socket is OPEN', () => {
    const close = vi.fn();
    const ws = {
      readyState: WebSocket.OPEN,
      onopen: null,
      onmessage: null,
      onclose: null,
      onerror: null,
      close,
      addEventListener: vi.fn(),
    } as unknown as WebSocket;

    const wsRef = { current: ws };

    closeWebSocketSafely(wsRef);

    expect(close).toHaveBeenCalledTimes(1);
    expect(wsRef.current).toBeNull();
  });
});
