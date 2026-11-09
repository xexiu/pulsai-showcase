'use client';

// =============================================================================
// Navigation Loading Hook - Detects navigation start immediately on click
// =============================================================================
//
// ARCHITECT NOTES (based on eScribAI2 pattern):
// - hasStarted: click detected (IMMEDIATE feedback)
// - isPageLoaded: DOM content ready (using requestIdleCallback/RAF)
// - Formula: showLoading = hasStarted && !isPageLoaded
// - This prevents stuck loading states
// =============================================================================

import { useCallback, useEffect, useRef, useState } from 'react';

import { usePathname } from 'next/navigation';

import { DEBOUNCE_MS } from '@/utils/constants';

interface UseNavigationLoadingResult {
  isNavigating: boolean;
  reset: () => void;
}

/**
 * Check if href is an external or special link that shouldn't trigger loading
 * @internal Exported for testing
 */
export function isExternalOrSpecialLink(href: string): boolean {
  return (
    href.startsWith('http://') ||
    href.startsWith('https://') ||
    href.startsWith('mailto:') ||
    href.startsWith('tel:') ||
    href.includes('#')
  );
}

/**
 * In-page / fragment navigation — never show the route transition overlay.
 * Any `#` in the attribute or resolved URL means "same document" for our purposes.
 *
 * @internal Exported for testing
 */
export function isFragmentNavigationLink(link: Element, hrefAttr: string): boolean {
  if (hrefAttr.includes('#')) {
    return true;
  }
  if (link instanceof HTMLAnchorElement && link.href.includes('#')) {
    return true;
  }

  return false;
}

/**
 * Normalize path for comparison (removes locale prefix)
 * @internal Exported for testing
 */
function normalizePathForComparison(path: string): string {
  // Remove locale prefix like /en/, /es/, /fr/, etc.
  // Matches: /xx/ or /xx at start where xx is 2-3 letter code
  return path.replace(/^\/[a-z]{2,3}(\/|$)/, '/');
}

/**
 * Check if the link should trigger navigation loading
 * @internal Exported for testing
 */
export function shouldTriggerLoading(link: Element, href: string, currentPath: string): boolean {
  if (isFragmentNavigationLink(link, href)) {
    return false;
  }

  if (isExternalOrSpecialLink(href)) {
    return false;
  }

  // Normalize paths to handle locale prefixes
  // e.g., /dashboard should match /es/dashboard
  const normalizedHref = normalizePathForComparison(href);
  const normalizedCurrent = normalizePathForComparison(currentPath);
  const normalizedWindowPath = normalizePathForComparison(window.location.pathname);

  if (normalizedHref === normalizedCurrent || normalizedHref === normalizedWindowPath) {
    return false;
  }
  if (link.getAttribute('target') === '_blank') {
    return false;
  }

  return true;
}

/**
 * Use requestIdleCallback with fallback for Safari
 */
function onIdle(callback: () => void): void {
  if ('requestIdleCallback' in window) {
    window.requestIdleCallback(callback, { timeout: 500 });
  } else {
    // Fallback: RAF + setTimeout for Safari
    requestAnimationFrame(() => {
      setTimeout(callback, DEBOUNCE_MS.FAST);
    });
  }
}

/**
 * Hook to detect navigation loading state
 *
 * Follows eScribAI2 pattern for robust loading detection:
 * - IMMEDIATE feedback on click (before route change)
 * - Page load detection using requestIdleCallback
 * - Prevents stuck loading states with multiple safety nets
 */
export function useNavigationLoading(): UseNavigationLoadingResult {
  const pathname = usePathname();
  const [hasStarted, setHasStarted] = useState(false);
  const [isPageLoaded, setIsPageLoaded] = useState(true);
  const prevPathnameRef = useRef(pathname);
  const maxTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Clear any pending timeout
  const clearMaxTimeout = useCallback((): void => {
    if (maxTimeoutRef.current) {
      clearTimeout(maxTimeoutRef.current);
      maxTimeoutRef.current = null;
    }
  }, []);

  const reset = useCallback((): void => {
    setHasStarted(false);
    setIsPageLoaded(true);
    clearMaxTimeout();
  }, [clearMaxTimeout]);

  // Listen for link clicks and popstate
  useEffect(() => {
    function handleClick(event: MouseEvent): void {
      const target = event.target as HTMLElement;
      const link = target.closest('a[href]');
      const href = link?.getAttribute('href');

      if (link && href && shouldTriggerLoading(link, href, pathname)) {
        setHasStarted(true);
        setIsPageLoaded(false);
        clearMaxTimeout();

        // Safety: max 5 seconds loading, then force reset
        maxTimeoutRef.current = setTimeout(reset, DEBOUNCE_MS.NAVIGATION_TIMEOUT);
      }
    }

    function handlePopState(): void {
      // Hash-only or same-path history changes don't swap the Next route; no overlay.
      if (
        normalizePathForComparison(window.location.pathname) ===
        normalizePathForComparison(pathname)
      ) {
        return;
      }

      setHasStarted(true);
      setIsPageLoaded(false);
      clearMaxTimeout();
      maxTimeoutRef.current = setTimeout(reset, DEBOUNCE_MS.NAVIGATION_TIMEOUT);
    }

    document.addEventListener('click', handleClick, true);
    window.addEventListener('popstate', handlePopState);

    return () => {
      document.removeEventListener('click', handleClick, true);
      window.removeEventListener('popstate', handlePopState);
      clearMaxTimeout();
    };
  }, [pathname, clearMaxTimeout, reset]);

  // Detect route change and page load completion
  useEffect(() => {
    if (prevPathnameRef.current !== pathname) {
      prevPathnameRef.current = pathname;

      // Wait for browser idle (DOM painted and stable)
      onIdle(() => {
        setIsPageLoaded(true);
        setHasStarted(false);
        clearMaxTimeout();
      });
    }
  }, [pathname, clearMaxTimeout]);

  // isNavigating = started but not yet loaded
  const isNavigating = hasStarted && !isPageLoaded;

  return { isNavigating, reset };
}
