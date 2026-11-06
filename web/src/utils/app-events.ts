/**
 * Application Event Bus
 *
 * Centralized, type-safe event system for cross-component communication.
 *
 * Architecture Principles:
 * - Single Responsibility: Only handles event dispatch/subscription
 * - Open/Closed: Add new events by extending types, not modifying code
 * - Dependency Inversion: Components depend on this abstraction
 * - Type Safety: Each event has strongly-typed payload
 *
 * Performance Considerations:
 * - Uses native browser CustomEvent (highly optimized)
 * - Ref pattern prevents re-subscription on handler changes
 * - No memory leaks: cleanup on unmount
 * - Selective subscription: components only receive events they subscribe to
 *
 * @example
 * // Dispatch events
 * dispatchAppEvent('session-expired');
 * dispatchAppEvent('signal-generated', { symbol: 'BTC/USDT', action: 'BUY' });
 *
 * @example
 * // Subscribe to events in React components
 * useAppEventListener('session-expired', () => {
 *   router.push('/login');
 * });
 */

'use client';

import { useEffect, useRef } from 'react';

// =============================================================================
// EVENT TYPE DEFINITIONS
// =============================================================================

/**
 * All application event types.
 * Organized by domain for clarity.
 */
export type AppEventType =
  // Auth Events
  | 'session-expired' // When JWT token expires mid-session
  | 'legal-consent-required' // Backend returned LEGAL_CONSENT_REQUIRED — refetch /me
  | 'auth-error' // Generic auth error (401 from API)
  // Signal Events (future use)
  | 'signal-generated' // New signal from WebSocket
  | 'signal-updated' // Signal outcome evaluated
  // Notification Events (future use)
  | 'notification-received' // Push notification
  | 'toast-show'; // Show toast message

/**
 * Signal action type
 */
type SignalAction = 'BUY' | 'SELL' | 'HOLD';

/**
 * Toast type for styling
 */
export type ToastType = 'success' | 'error' | 'warning' | 'info';

/**
 * Payload types for each event.
 * Events without payloads use `void`.
 */
export interface AppEventPayloads {
  // -------------------------------------------------------------------------
  // Auth Events
  // -------------------------------------------------------------------------
  /** Fired when session expires mid-use. No payload - triggers redirect */
  'session-expired': void;

  /** Fired when API returns LEGAL_CONSENT_REQUIRED — AuthProvider refetches profile */
  'legal-consent-required': void;

  /** Fired on 401 errors from API */
  'auth-error': {
    /** Error message */
    message: string;
    /** HTTP status code */
    status?: number;
  };

  // -------------------------------------------------------------------------
  // Signal Events (future)
  // -------------------------------------------------------------------------
  /** New signal generated */
  'signal-generated': {
    /** Trading pair (e.g., "BTC/USDT") */
    symbol: string;
    /** Signal action */
    action: SignalAction;
    /** Confidence percentage */
    confidence: number;
    /** Timeframe */
    timeframe: string;
  };

  /** Signal outcome evaluated */
  'signal-updated': {
    /** Signal ID */
    signalId: string;
    /** Whether prediction was correct */
    outcome: 'correct' | 'incorrect' | 'pending';
  };

  // -------------------------------------------------------------------------
  // Notification Events (future)
  // -------------------------------------------------------------------------
  /** Push notification received */
  'notification-received': {
    /** Notification title */
    title: string;
    /** Notification body */
    body: string;
    /** Optional action URL */
    actionUrl?: string;
  };

  /** Show toast notification */
  'toast-show': {
    /** Toast message */
    message: string;
    /** Toast type */
    type: ToastType;
    /** Duration in ms (optional, default 5000) */
    duration?: number;
  };
}

// =============================================================================
// EVENT DISPATCH
// =============================================================================

/**
 * Dispatch an application event.
 * Type-safe: TypeScript will enforce correct payload for each event type.
 *
 * @param type - The event type to dispatch
 * @param payload - Payload (required for events with payload, forbidden for void events)
 *
 * @example
 * dispatchAppEvent('session-expired');
 * dispatchAppEvent('signal-generated', { symbol: 'BTC/USDT', action: 'BUY', confidence: 75, timeframe: '1h' });
 */
export function dispatchAppEvent<T extends AppEventType>(
  type: T,
  ...args: AppEventPayloads[T] extends void ? [] : [payload: AppEventPayloads[T]]
): void {
  if (typeof window === 'undefined') {
    return;
  }

  const payload = args[0];

  window.dispatchEvent(new CustomEvent(type, { detail: payload }));
}

// =============================================================================
// EVENT SUBSCRIPTION HOOK
// =============================================================================

/**
 * Options for useAppEventListener hook.
 */
export interface UseAppEventListenerOptions {
  /**
   * Whether the listener is enabled. Default: true.
   * Useful for conditionally enabling/disabling listeners.
   */
  enabled?: boolean;
}

/**
 * React hook to subscribe to application events.
 * Automatically handles cleanup on unmount.
 *
 * Performance optimizations:
 * - Uses ref pattern to avoid re-subscribing when handler changes
 * - Only re-subscribes when event type or enabled changes
 * - Clean memory management with cleanup on unmount
 *
 * @param type - The event type to listen for
 * @param handler - Callback function when event is dispatched
 * @param options - Optional configuration (enabled)
 *
 * @example
 * // Basic usage (void event)
 * useAppEventListener('session-expired', () => {
 *   router.push('/login');
 * });
 *
 * @example
 * // With payload
 * useAppEventListener('signal-generated', (payload) => {
 *   toast.success(`${payload.action} signal for ${payload.symbol}!`);
 * });
 *
 * @example
 * // Conditionally enabled
 * useAppEventListener('notification-received', handleNotification, { enabled: isAdmin });
 */
export function useAppEventListener<T extends AppEventType>(
  type: T,
  handler: AppEventPayloads[T] extends void ? () => void : (payload: AppEventPayloads[T]) => void,
  options: UseAppEventListenerOptions = {}
): void {
  const { enabled = true } = options;

  // Use ref to always have the latest handler without re-subscribing
  const handlerRef = useRef(handler);

  // Update ref when handler changes (no re-subscription needed)
  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  // Subscribe to event (only re-subscribes when type or enabled changes)
  useEffect(() => {
    // Early return if disabled or SSR
    if (!enabled || typeof window === 'undefined') {
      return;
    }

    const listener = (event: Event): void => {
      const customEvent = event as CustomEvent<AppEventPayloads[T]>;
      const { detail } = customEvent;

      // Handle void events (detail is null/undefined)
      if (detail === null || detail === undefined) {
        (handlerRef.current as () => void)();
      } else {
        (handlerRef.current as (payload: AppEventPayloads[T]) => void)(detail);
      }
    };

    window.addEventListener(type, listener);

    return () => {
      window.removeEventListener(type, listener);
    };
  }, [type, enabled]);
}

// =============================================================================
// CONVENIENCE FUNCTIONS - Auth Events
// =============================================================================

/**
 * Dispatch session-expired event.
 * Call this when JWT token expires mid-session.
 * AuthProvider listens for this to trigger logout/redirect.
 */
export function dispatchSessionExpired(): void {
  dispatchAppEvent('session-expired');
}

/**
 * Dispatch auth-error event.
 * Call this on 401 responses from API.
 */
export function dispatchAuthError(message: string, status?: number): void {
  // Build payload without undefined values (strictOptionalPropertyTypes)
  const payload: AppEventPayloads['auth-error'] = { message };

  if (status !== undefined) {
    payload.status = status;
  }
  dispatchAppEvent('auth-error', payload);
}

// =============================================================================
// CONVENIENCE FUNCTIONS - Toast Events
// =============================================================================

/**
 * Dispatch toast-show event.
 * Use this to show toasts from anywhere in the app.
 */
export function dispatchToast(message: string, type: ToastType = 'info', duration?: number): void {
  // Build payload without undefined values (strictOptionalPropertyTypes)
  const payload: AppEventPayloads['toast-show'] = { message, type };

  if (duration !== undefined) {
    payload.duration = duration;
  }
  dispatchAppEvent('toast-show', payload);
}
