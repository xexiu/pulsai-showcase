/**
 * Page visibility session — SoT for tab/PWA background vs foreground timing.
 *
 * Used to suppress WebSocket lifecycle toasts and pause sockets while hidden.
 */

export const PAGE_VISIBILITY_BACKGROUND_TOAST_SUPPRESS_MS = 30_000;
export const PAGE_VISIBILITY_RETURN_GRACE_MS = 5_000;

type PageVisibilityListener = (hidden: boolean) => void;

const listeners = new Set<PageVisibilityListener>();

let lastHiddenAt: number | null = null;
let lastVisibleAt: number | null = null;

export function resetPageVisibilitySessionForTests(): void {
  lastHiddenAt = null;
  lastVisibleAt = null;
  listeners.clear();
}

export function markDocumentHidden(now: number = Date.now()): void {
  lastHiddenAt = now;
}

export function markDocumentVisible(now: number = Date.now()): void {
  lastVisibleAt = now;
}

function isDocumentHidden(): boolean {
  if (typeof document === 'undefined') {
    return false;
  }

  return document.hidden;
}

/**
 * Suppress signals WebSocket connected/disconnected toasts after a brief background.
 */
export function shouldSuppressWebSocketLifecycleToast(now: number = Date.now()): boolean {
  if (lastHiddenAt === null) {
    return false;
  }

  if (isDocumentHidden()) {
    return true;
  }

  const hiddenEndedAt = lastVisibleAt ?? now;
  const hiddenDurationMs = hiddenEndedAt - lastHiddenAt;

  if (hiddenDurationMs > PAGE_VISIBILITY_BACKGROUND_TOAST_SUPPRESS_MS) {
    return false;
  }

  if (lastVisibleAt === null) {
    return true;
  }

  return now - lastVisibleAt < PAGE_VISIBILITY_RETURN_GRACE_MS;
}

function subscribePageVisibility(listener: PageVisibilityListener): () => void {
  listeners.add(listener);
  listener(isDocumentHidden());

  return () => {
    listeners.delete(listener);
  };
}

export type PageVisibilityWebSocketPauseBindings = {
  isPausedByVisibility: () => boolean;
  setPausedByVisibility: (paused: boolean) => void;
  onVisibilityPause: () => void;
  onVisibilityResume: () => void;
};

/** Skip opening a socket while the tab is hidden or paused for visibility. */
export function shouldDeferWebSocketConnectForPageVisibility(
  isPausedByVisibility: boolean
): boolean {
  return isPausedByVisibility || isDocumentHidden();
}

/**
 * Pause/resume WebSocket lifecycle when the document visibility changes.
 * Shared by Binance candles and signals sockets (DRY).
 */
export function subscribePageVisibilityWebSocketPause(
  bindings: PageVisibilityWebSocketPauseBindings
): () => void {
  return subscribePageVisibility((hidden) => {
    if (hidden) {
      bindings.setPausedByVisibility(true);
      bindings.onVisibilityPause();

      return;
    }

    if (!bindings.isPausedByVisibility()) return;

    bindings.setPausedByVisibility(false);
    bindings.onVisibilityResume();
  });
}

function notifyPageVisibilityListeners(hidden: boolean): void {
  for (const listener of listeners) {
    listener(hidden);
  }
}

/**
 * Attach document visibility listeners once per client session.
 */
export function initPageVisibilitySession(): () => void {
  if (typeof document === 'undefined') {
    return () => {};
  }

  const handleVisibilityChange = (): void => {
    if (document.hidden) {
      markDocumentHidden();
      notifyPageVisibilityListeners(true);

      return;
    }

    markDocumentVisible();
    notifyPageVisibilityListeners(false);
  };

  document.addEventListener('visibilitychange', handleVisibilityChange);

  return () => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  };
}
