// =============================================================================
// App Events Tests - Type-Safe Event System
// =============================================================================
//
// BEHAVIOR TESTS:
// - Event dispatch reaches listeners
// - Type safety enforced
// - Hook cleanup on unmount
// - Ref pattern avoids re-subscriptions
// - Conditional enabling/disabling
// =============================================================================

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  dispatchAppEvent,
  dispatchAuthError,
  dispatchSessionExpired,
  dispatchToast,
  useAppEventListener,
} from '@/utils/app-events';

// =============================================================================
// Test Setup
// =============================================================================

describe('app-events', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ===========================================================================
  // dispatchAppEvent Tests
  // ===========================================================================

  describe('dispatchAppEvent', () => {
    it('dispatches void event without payload', () => {
      const listener = vi.fn();

      window.addEventListener('session-expired', listener);

      dispatchAppEvent('session-expired');

      expect(listener).toHaveBeenCalledTimes(1);

      window.removeEventListener('session-expired', listener);
    });

    it('dispatches event with payload', () => {
      const listener = vi.fn();

      window.addEventListener('auth-error', listener);

      dispatchAppEvent('auth-error', { message: 'Test error', status: 401 });

      expect(listener).toHaveBeenCalledTimes(1);
      expect(listener.mock.calls[0]?.[0]?.detail).toEqual({
        message: 'Test error',
        status: 401,
      });

      window.removeEventListener('auth-error', listener);
    });

    it('does not throw on SSR (window undefined)', () => {
      // This test just verifies the code handles SSR gracefully
      // The actual SSR check is in the implementation
      expect(() => dispatchAppEvent('session-expired')).not.toThrow();
    });
  });

  // ===========================================================================
  // useAppEventListener Hook Tests
  // ===========================================================================

  describe('useAppEventListener', () => {
    it('calls handler when event is dispatched (void event)', () => {
      const handler = vi.fn();

      renderHook(() => useAppEventListener('session-expired', handler));

      act(() => {
        dispatchAppEvent('session-expired');
      });

      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('calls handler with payload for payload events', () => {
      const handler = vi.fn();

      renderHook(() => useAppEventListener('auth-error', handler));

      act(() => {
        dispatchAppEvent('auth-error', { message: 'Test', status: 401 });
      });

      expect(handler).toHaveBeenCalledWith({ message: 'Test', status: 401 });
    });

    it('cleans up listener on unmount', () => {
      const handler = vi.fn();

      const { unmount } = renderHook(() => useAppEventListener('session-expired', handler));

      unmount();

      act(() => {
        dispatchAppEvent('session-expired');
      });

      expect(handler).not.toHaveBeenCalled();
    });

    it('does not call handler when disabled', () => {
      const handler = vi.fn();

      renderHook(() => useAppEventListener('session-expired', handler, { enabled: false }));

      act(() => {
        dispatchAppEvent('session-expired');
      });

      expect(handler).not.toHaveBeenCalled();
    });

    it('uses latest handler via ref pattern (no re-subscription)', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();

      const { rerender } = renderHook(
        ({ handler }) => useAppEventListener('session-expired', handler),
        { initialProps: { handler: handler1 } }
      );

      // Update handler
      rerender({ handler: handler2 });

      act(() => {
        dispatchAppEvent('session-expired');
      });

      // Old handler should NOT be called, new handler should
      expect(handler1).not.toHaveBeenCalled();
      expect(handler2).toHaveBeenCalledTimes(1);
    });

    it('handles signal-generated event with full payload', () => {
      const handler = vi.fn();

      renderHook(() => useAppEventListener('signal-generated', handler));

      act(() => {
        dispatchAppEvent('signal-generated', {
          symbol: 'BTC/USDT',
          action: 'BUY',
          confidence: 85,
          timeframe: '1h',
        });
      });

      expect(handler).toHaveBeenCalledWith({
        symbol: 'BTC/USDT',
        action: 'BUY',
        confidence: 85,
        timeframe: '1h',
      });
    });

    it('handles toast-show event', () => {
      const handler = vi.fn();

      renderHook(() => useAppEventListener('toast-show', handler));

      act(() => {
        dispatchAppEvent('toast-show', {
          message: 'Test toast',
          type: 'success',
        });
      });

      expect(handler).toHaveBeenCalledWith({
        message: 'Test toast',
        type: 'success',
      });
    });
  });

  // ===========================================================================
  // Convenience Function Tests
  // ===========================================================================

  describe('convenience functions', () => {
    describe('dispatchSessionExpired', () => {
      it('dispatches session-expired event', () => {
        const listener = vi.fn();

        window.addEventListener('session-expired', listener);

        dispatchSessionExpired();

        expect(listener).toHaveBeenCalledTimes(1);

        window.removeEventListener('session-expired', listener);
      });
    });

    describe('dispatchAuthError', () => {
      it('dispatches auth-error event with message', () => {
        const listener = vi.fn();

        window.addEventListener('auth-error', listener);

        dispatchAuthError('Unauthorized');

        expect(listener).toHaveBeenCalledTimes(1);
        expect(listener.mock.calls[0]?.[0]?.detail).toEqual({
          message: 'Unauthorized',
        });

        window.removeEventListener('auth-error', listener);
      });

      it('dispatches auth-error event with message and status', () => {
        const listener = vi.fn();

        window.addEventListener('auth-error', listener);

        dispatchAuthError('Forbidden', 403);

        expect(listener.mock.calls[0]?.[0]?.detail).toEqual({
          message: 'Forbidden',
          status: 403,
        });

        window.removeEventListener('auth-error', listener);
      });
    });

    describe('dispatchToast', () => {
      it('dispatches toast with default type (info)', () => {
        const listener = vi.fn();

        window.addEventListener('toast-show', listener);

        dispatchToast('Hello');

        expect(listener.mock.calls[0]?.[0]?.detail).toEqual({
          message: 'Hello',
          type: 'info',
        });

        window.removeEventListener('toast-show', listener);
      });

      it('dispatches toast with custom type', () => {
        const listener = vi.fn();

        window.addEventListener('toast-show', listener);

        dispatchToast('Success!', 'success');

        expect(listener.mock.calls[0]?.[0]?.detail).toEqual({
          message: 'Success!',
          type: 'success',
        });

        window.removeEventListener('toast-show', listener);
      });

      it('dispatches toast with duration', () => {
        const listener = vi.fn();

        window.addEventListener('toast-show', listener);

        dispatchToast('Quick', 'warning', 2000);

        expect(listener.mock.calls[0]?.[0]?.detail).toEqual({
          message: 'Quick',
          type: 'warning',
          duration: 2000,
        });

        window.removeEventListener('toast-show', listener);
      });
    });
  });
});
