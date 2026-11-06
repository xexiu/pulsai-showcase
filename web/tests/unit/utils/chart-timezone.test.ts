// =============================================================================
// chart-timezone utils tests
// =============================================================================

import {
  CHART_BAR_RAW_UTC_MIN_MINUTES,
  shouldChartBarTimesUseLegacyTimeToTz,
} from '@pulsai/shared';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildChartLocalizationOptions,
  getChartTimeAxisFormatterZone,
  getChartTimezone,
  setChartTimezone,
  shouldApplyTimeToTzForTimeframe,
  timeToTz,
} from '@/utils/chart-timezone';
import { STORAGE_KEYS } from '@/utils/constants';

const KEY = STORAGE_KEYS.CHART_TIMEZONE;

describe('getChartTimezone', () => {
  beforeEach(() => {
    localStorage.removeItem(KEY);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns stored value when localStorage has CHART_TIMEZONE', () => {
    localStorage.setItem(KEY, 'Europe/Madrid');

    expect(getChartTimezone()).toBe('Europe/Madrid');
  });

  it('returns Intl fallback when localStorage is empty', () => {
    const resolved = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const tz = getChartTimezone();

    expect(tz).toBe(resolved);
    expect(typeof tz).toBe('string');
    expect(tz.length).toBeGreaterThan(0);
  });

  it('returns UTC when window is undefined (SSR)', () => {
    const originalWindow = globalThis.window;

    // @ts-expect-error - simulating SSR
    delete globalThis.window;

    const tz = getChartTimezone();

    expect(tz).toBe('UTC');
    globalThis.window = originalWindow;
  });
});

describe('setChartTimezone', () => {
  beforeEach(() => {
    localStorage.removeItem(KEY);
  });

  it('calls localStorage.setItem with correct key and value', () => {
    setChartTimezone('America/New_York');

    expect(localStorage.getItem(KEY)).toBe('America/New_York');
  });

  it('does not throw when localStorage throws', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    expect(() => setChartTimezone('Europe/London')).not.toThrow();
    setItem.mockRestore();
  });

  it('is no-op when window is undefined (SSR)', () => {
    const originalWindow = globalThis.window;
    const setItem = vi.spyOn(Storage.prototype, 'setItem');

    // @ts-expect-error - simulating SSR
    delete globalThis.window;

    setChartTimezone('Asia/Tokyo');

    expect(setItem).not.toHaveBeenCalled();
    globalThis.window = originalWindow;
    setItem.mockRestore();
  });
});

describe('buildChartLocalizationOptions', () => {
  it('returns object with localization.timeFormatter', () => {
    const opts = buildChartLocalizationOptions('UTC');

    expect(opts).toHaveProperty('localization');
    expect(opts.localization).toHaveProperty('timeFormatter');
    expect(typeof opts.localization.timeFormatter).toBe('function');
  });

  it('formatter returns string for known UTC second', () => {
    const opts = buildChartLocalizationOptions('Europe/Madrid');
    // 2024-06-15 12:00:00 UTC
    const utcSeconds = 1718452800;

    const formatted = opts.localization.timeFormatter(utcSeconds);

    expect(typeof formatted).toBe('string');
    expect(formatted.length).toBeGreaterThan(0);
    // Should contain date/time parts (month, day, hour, minute)
    expect(formatted).toMatch(/\d/);
  });
});

describe('timeToTz', () => {
  it('converts UTC to local-time-as-UTC for Europe/Madrid', () => {
    // 2024-01-15 19:00:00 UTC = 20:00 in Madrid (winter UTC+1)
    const utcSeconds = 1705345200;
    const result = timeToTz(utcSeconds, 'Europe/Madrid');
    const d = new Date(result * 1000);

    expect(Number.isInteger(result)).toBe(true);
    expect(d.getUTCHours()).toBe(20);
    expect(d.getUTCMinutes()).toBe(0);
  });

  it('is deterministic for same input and timezone', () => {
    const utcSeconds = 1705345200;

    expect(timeToTz(utcSeconds, 'Europe/Madrid')).toBe(timeToTz(utcSeconds, 'Europe/Madrid'));
  });

  it('UTC zone preserves wall-clock (same instant = same local components in UTC)', () => {
    const utcSeconds = 1705345200;

    expect(timeToTz(utcSeconds, 'UTC')).toBe(utcSeconds);
  });
});

describe('shouldApplyTimeToTzForTimeframe', () => {
  it('matches @pulsai/shared SoT (shouldChartBarTimesUseLegacyTimeToTz)', () => {
    for (const tf of ['1h', '15m', '4h', '1d', '1w'] as const) {
      expect(shouldApplyTimeToTzForTimeframe(tf)).toBe(shouldChartBarTimesUseLegacyTimeToTz(tf));
    }
    expect(shouldApplyTimeToTzForTimeframe(undefined)).toBe(
      shouldChartBarTimesUseLegacyTimeToTz(undefined)
    );
    expect(shouldApplyTimeToTzForTimeframe('')).toBe(shouldChartBarTimesUseLegacyTimeToTz(''));
  });

  it('returns true for short intraday timeframes (below 4h)', () => {
    expect(shouldApplyTimeToTzForTimeframe('1h')).toBe(true);
    expect(shouldApplyTimeToTzForTimeframe('15m')).toBe(true);
  });

  it('returns false for 4h and above (raw UTC bar times for even spacing)', () => {
    expect(CHART_BAR_RAW_UTC_MIN_MINUTES).toBe(240);
    expect(shouldApplyTimeToTzForTimeframe('4h')).toBe(false);
    expect(shouldApplyTimeToTzForTimeframe('1d')).toBe(false);
    expect(shouldApplyTimeToTzForTimeframe('1w')).toBe(false);
  });

  it('returns true for undefined or empty (legacy safe default)', () => {
    expect(shouldApplyTimeToTzForTimeframe(undefined)).toBe(true);
    expect(shouldApplyTimeToTzForTimeframe('')).toBe(true);
  });
});

describe('getChartTimeAxisFormatterZone', () => {
  it('returns UTC when short intraday uses timeToTz on bar times', () => {
    expect(getChartTimeAxisFormatterZone('Europe/Madrid', '1h')).toBe('UTC');
  });

  it('returns user zone for 4h+ when bars use raw UTC', () => {
    expect(getChartTimeAxisFormatterZone('Europe/Madrid', '4h')).toBe('Europe/Madrid');
    expect(getChartTimeAxisFormatterZone('Europe/Madrid', '1w')).toBe('Europe/Madrid');
  });
});
