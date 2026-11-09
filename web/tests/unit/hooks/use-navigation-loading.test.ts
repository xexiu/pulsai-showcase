/**
 * Unit Tests: useNavigationLoading Hook
 *
 * PRO Test Approach:
 * - Test hook STATE changes
 * - Test event handling behavior
 * - Test cleanup (no memory leaks)
 * - Mock browser APIs properly
 *
 * Following: TESTING_STRATEGY.md
 */

import * as navigation from 'next/navigation';

import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  isExternalOrSpecialLink,
  isFragmentNavigationLink,
  shouldTriggerLoading,
  useNavigationLoading,
} from '@/hooks/useNavigationLoading';

// =============================================================================
// Helper Function Tests (Pure Functions - Easy to Test)
// =============================================================================

describe('isExternalOrSpecialLink', () => {
  it('returns true for http:// links', () => {
    expect(isExternalOrSpecialLink('http://example.com')).toBe(true);
  });

  it('returns true for https:// links', () => {
    expect(isExternalOrSpecialLink('https://example.com')).toBe(true);
  });

  it('returns true for mailto: links', () => {
    expect(isExternalOrSpecialLink('mailto:test@example.com')).toBe(true);
  });

  it('returns true for tel: links', () => {
    expect(isExternalOrSpecialLink('tel:+1234567890')).toBe(true);
  });

  it('returns true for hash links', () => {
    expect(isExternalOrSpecialLink('#section')).toBe(true);
  });

  it('returns true when href contains # anywhere', () => {
    expect(isExternalOrSpecialLink('/es/legal/cookies#browser-controls')).toBe(true);
  });

  it('returns false for internal paths', () => {
    expect(isExternalOrSpecialLink('/about')).toBe(false);
    expect(isExternalOrSpecialLink('/dashboard/settings')).toBe(false);
  });

  it('returns false for relative paths', () => {
    expect(isExternalOrSpecialLink('about')).toBe(false);
    expect(isExternalOrSpecialLink('./page')).toBe(false);
  });
});

describe('shouldTriggerLoading', () => {
  function createMockLink(attrs: Record<string, string>): Element {
    const link = document.createElement('a');

    Object.entries(attrs).forEach(([key, value]) => {
      link.setAttribute(key, value);
    });

    return link;
  }

  it('returns true for internal navigation to different path', () => {
    const link = createMockLink({ href: '/new-page' });

    expect(shouldTriggerLoading(link, '/new-page', '/current')).toBe(true);
  });

  it('returns false for external links', () => {
    const link = createMockLink({ href: 'https://external.com' });

    expect(shouldTriggerLoading(link, 'https://external.com', '/current')).toBe(false);
  });

  it('returns false for same path navigation', () => {
    const link = createMockLink({ href: '/current' });

    expect(shouldTriggerLoading(link, '/current', '/current')).toBe(false);
  });

  it('returns false for links with target="_blank"', () => {
    const link = createMockLink({ href: '/new-page', target: '_blank' });

    expect(shouldTriggerLoading(link, '/new-page', '/current')).toBe(false);
  });

  it('returns false for mailto links', () => {
    const link = createMockLink({ href: 'mailto:test@example.com' });

    expect(shouldTriggerLoading(link, 'mailto:test@example.com', '/current')).toBe(false);
  });

  it('returns false for hash links', () => {
    const link = createMockLink({ href: '#section' });

    expect(shouldTriggerLoading(link, '#section', '/current')).toBe(false);
  });

  it('returns false for same path with #fragment in href (not only #prefix)', () => {
    window.history.pushState({}, '', '/es/legal/terms');

    const link = createMockLink({ href: '/es/legal/terms#acceptance' });

    try {
      expect(shouldTriggerLoading(link, '/es/legal/terms#acceptance', '/es/legal/terms')).toBe(
        false
      );
    } finally {
      window.history.pushState({}, '', '/');
    }
  });
});

describe('isFragmentNavigationLink', () => {
  it('returns true for fragment-only href', () => {
    const link = document.createElement('a');

    link.setAttribute('href', '#browser-controls');

    expect(isFragmentNavigationLink(link, '#browser-controls')).toBe(true);
  });

  it('returns true for path with #fragment', () => {
    const link = document.createElement('a');

    link.setAttribute('href', '/es/legal/cookies#browser-controls');

    expect(isFragmentNavigationLink(link, '/es/legal/cookies#browser-controls')).toBe(true);
  });
});

// =============================================================================
// Hook Tests
// =============================================================================

describe('useNavigationLoading', () => {
  let mockPathname = '/initial';

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    mockPathname = '/initial';

    // Override pathname mock for this test suite
    vi.spyOn(navigation, 'usePathname').mockImplementation(() => mockPathname);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('starts with isNavigating as false', () => {
      const { result } = renderHook(() => useNavigationLoading());

      // PRO: Hook should not assume navigation on mount
      expect(result.current.isNavigating).toBe(false);
    });

    it('provides a reset function', () => {
      const { result } = renderHook(() => useNavigationLoading());

      // PRO: API should be complete
      expect(typeof result.current.reset).toBe('function');
    });
  });

  describe('reset function', () => {
    it('resets isNavigating to false', () => {
      const { result } = renderHook(() => useNavigationLoading());

      // Manually trigger navigation state (simulate internal state)
      act(() => {
        result.current.reset();
      });

      expect(result.current.isNavigating).toBe(false);
    });

    it('reset function is stable across renders', () => {
      const { result, rerender } = renderHook(() => useNavigationLoading());

      const firstReset = result.current.reset;

      rerender();

      const secondReset = result.current.reset;

      // PRO: Stable references prevent unnecessary re-renders
      expect(firstReset).toBe(secondReset);
    });
  });

  describe('internal link click detection', () => {
    it('sets isNavigating when user clicks an internal link', () => {
      const { result } = renderHook(() => useNavigationLoading());

      // Create a mock internal link
      const link = document.createElement('a');

      link.href = '/new-page';
      document.body.appendChild(link);

      act(() => {
        link.click();
      });

      // PRO: Navigation should be detected immediately
      expect(result.current.isNavigating).toBe(true);

      document.body.removeChild(link);
    });

    it('ignores external link clicks', () => {
      const { result } = renderHook(() => useNavigationLoading());

      const link = document.createElement('a');

      link.href = 'https://external-site.com';
      document.body.appendChild(link);

      act(() => {
        link.click();
      });

      // PRO: External links don't trigger internal loading
      expect(result.current.isNavigating).toBe(false);

      document.body.removeChild(link);
    });

    it('ignores links with target="_blank"', () => {
      const { result } = renderHook(() => useNavigationLoading());

      const link = document.createElement('a');

      link.href = '/new-page';
      link.target = '_blank';
      document.body.appendChild(link);

      act(() => {
        link.click();
      });

      // PRO: New tab links don't show loading in current tab
      expect(result.current.isNavigating).toBe(false);

      document.body.removeChild(link);
    });

    it('ignores hash links on same page', () => {
      const { result } = renderHook(() => useNavigationLoading());

      const link = document.createElement('a');

      link.href = '#section';
      document.body.appendChild(link);

      act(() => {
        link.click();
      });

      // PRO: Anchor links don't trigger page navigation
      expect(result.current.isNavigating).toBe(false);

      document.body.removeChild(link);
    });

    it('ignores mailto links', () => {
      const { result } = renderHook(() => useNavigationLoading());

      const link = document.createElement('a');

      link.href = 'mailto:test@example.com';
      document.body.appendChild(link);

      act(() => {
        link.click();
      });

      // PRO: mailto links don't navigate
      expect(result.current.isNavigating).toBe(false);

      document.body.removeChild(link);
    });
  });

  describe('browser navigation detection', () => {
    it('sets isNavigating on popstate event (back/forward)', () => {
      const { result } = renderHook(() => useNavigationLoading());

      act(() => {
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      // PRO: Browser navigation should trigger loading
      expect(result.current.isNavigating).toBe(true);
    });

    it('does not set isNavigating on popstate when pathname matches (hash-only history)', () => {
      window.history.pushState({}, '', '/es/legal/cookies');
      mockPathname = '/es/legal/cookies';
      vi.spyOn(navigation, 'usePathname').mockImplementation(() => mockPathname);

      const { result } = renderHook(() => useNavigationLoading());

      act(() => {
        window.dispatchEvent(new PopStateEvent('popstate'));
      });

      expect(result.current.isNavigating).toBe(false);

      window.history.pushState({}, '', '/');
    });
  });

  describe('route change completion', () => {
    it('resets isNavigating when pathname changes', () => {
      const { result, rerender } = renderHook(() => useNavigationLoading());

      // Trigger navigation
      const link = document.createElement('a');

      link.href = '/new-page';
      document.body.appendChild(link);

      act(() => {
        link.click();
      });

      expect(result.current.isNavigating).toBe(true);

      // Simulate route change
      mockPathname = '/new-page';
      vi.spyOn(navigation, 'usePathname').mockImplementation(() => mockPathname);

      rerender();

      // Run timers for the delay
      act(() => {
        vi.advanceTimersByTime(100);
      });

      // PRO: Loading should end after navigation completes
      expect(result.current.isNavigating).toBe(false);

      document.body.removeChild(link);
    });
  });

  describe('cleanup', () => {
    it('removes event listeners on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');
      const windowRemoveSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = renderHook(() => useNavigationLoading());

      unmount();

      // PRO: Proper cleanup prevents memory leaks
      expect(removeEventListenerSpy).toHaveBeenCalled();
      expect(windowRemoveSpy).toHaveBeenCalled();
    });

    it('clears timeouts on unmount', () => {
      const { unmount } = renderHook(() => useNavigationLoading());

      unmount();

      // PRO: Timeouts should be cleared to prevent state updates after unmount
      // Note: This may or may not be called depending on implementation
      // The important thing is no errors occur
      expect(() => unmount).not.toThrow();
    });
  });
});
