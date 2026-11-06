// @vitest-environment node
import { afterEach, describe, expect, it } from 'vitest';

import {
  markDocumentHidden,
  markDocumentVisible,
  PAGE_VISIBILITY_BACKGROUND_TOAST_SUPPRESS_MS,
  PAGE_VISIBILITY_RETURN_GRACE_MS,
  resetPageVisibilitySessionForTests,
  shouldDeferWebSocketConnectForPageVisibility,
  shouldSuppressWebSocketLifecycleToast,
} from '@/utils/page-visibility-session';

describe('page-visibility-session', () => {
  afterEach(() => {
    resetPageVisibilitySessionForTests();
  });

  it('suppresses lifecycle toasts shortly after a brief background', () => {
    const hiddenAt = 1_000;
    const visibleAt = hiddenAt + 2_000;

    markDocumentHidden(hiddenAt);
    markDocumentVisible(visibleAt);

    expect(
      shouldSuppressWebSocketLifecycleToast(visibleAt + PAGE_VISIBILITY_RETURN_GRACE_MS - 1)
    ).toBe(true);
  });

  it('does not suppress lifecycle toasts after a long background', () => {
    const hiddenAt = 1_000;

    markDocumentHidden(hiddenAt);
    markDocumentVisible(hiddenAt + PAGE_VISIBILITY_BACKGROUND_TOAST_SUPPRESS_MS + 1);

    expect(shouldSuppressWebSocketLifecycleToast(hiddenAt + 60_000)).toBe(false);
  });

  it('defers websocket connect when paused for visibility', () => {
    expect(shouldDeferWebSocketConnectForPageVisibility(true)).toBe(true);
    expect(shouldDeferWebSocketConnectForPageVisibility(false)).toBe(false);
  });
});
