// @vitest-environment node
// =============================================================================
// intl-datetime-format-cache tests
// =============================================================================
//
// WHY THESE TESTS?
// - getCachedDateTimeFormat memoizes Intl.DateTimeFormat by (locale, options) so
//   chart hot paths (timeToTz per-bar, axis timeFormatter per-tick) stop allocating
//   a fresh formatter on every call.
// - BEHAVIOR contract: identical inputs -> SAME instance (so callers actually skip
//   construction), different inputs -> different instance, and formatted output is
//   byte-identical to a freshly constructed formatter (no regression).
// =============================================================================

import { beforeEach, describe, expect, it } from 'vitest';

import {
  __resetIntlDateTimeFormatCacheForTests,
  getCachedDateTimeFormat,
} from '@/utils/intl-datetime-format-cache';

describe('getCachedDateTimeFormat', () => {
  beforeEach(() => {
    __resetIntlDateTimeFormatCacheForTests();
  });

  it('returns the SAME instance for identical (locale, options) — the memoization contract', () => {
    const opts: Intl.DateTimeFormatOptions = {
      timeZone: 'Europe/Madrid',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    };

    const first = getCachedDateTimeFormat('en-CA', opts);
    const second = getCachedDateTimeFormat('en-CA', { ...opts });

    expect(second).toBe(first);
  });

  it('returns a DIFFERENT instance when the locale differs', () => {
    const opts: Intl.DateTimeFormatOptions = { timeZone: 'UTC', year: 'numeric' };

    const en = getCachedDateTimeFormat('en-US', opts);
    const es = getCachedDateTimeFormat('es-ES', opts);

    expect(es).not.toBe(en);
  });

  it('returns a DIFFERENT instance when the options differ', () => {
    const a = getCachedDateTimeFormat('en-US', { timeZone: 'UTC', hour: '2-digit' });
    const b = getCachedDateTimeFormat('en-US', { timeZone: 'UTC', minute: '2-digit' });

    expect(b).not.toBe(a);
  });

  it('treats a missing locale the same as undefined and reuses one instance', () => {
    const opts: Intl.DateTimeFormatOptions = { timeZone: 'UTC', day: '2-digit' };

    const first = getCachedDateTimeFormat(undefined, opts);
    const second = getCachedDateTimeFormat(undefined, opts);

    expect(second).toBe(first);
  });

  it('produces output byte-identical to a freshly constructed Intl.DateTimeFormat', () => {
    const opts: Intl.DateTimeFormatOptions = {
      timeZone: 'Europe/Madrid',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    };
    const date = new Date('2026-06-22T11:00:00.000Z');

    const cached = getCachedDateTimeFormat('en-CA', opts).format(date);
    const fresh = new Intl.DateTimeFormat('en-CA', opts).format(date);

    expect(cached).toBe(fresh);
  });

  it('produces formatToParts byte-identical to a fresh formatter', () => {
    const opts: Intl.DateTimeFormatOptions = {
      timeZone: 'America/New_York',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    };
    const date = new Date('2026-01-15T18:30:00.000Z');

    const cached = getCachedDateTimeFormat('en-US', opts).formatToParts(date);
    const fresh = new Intl.DateTimeFormat('en-US', opts).formatToParts(date);

    expect(cached).toEqual(fresh);
  });
});
