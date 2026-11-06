// @vitest-environment node
/**
 * datetime formatters — branch coverage for formatTime/formatDateTimeOrNull
 * /formatTimeAgo/formatUptime/formatNextRun/normalizeTimestamp/formatChartTooltipTime.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  formatChartTooltipTime,
  formatDateTime,
  formatDateTimeOrNull,
  formatNextRun,
  formatTime,
  formatTimeAgo,
  formatUptime,
  normalizeTimestamp,
} from '@/utils/formatters/datetime';

describe('formatTime', () => {
  it('renders the placeholder when date is null', () => {
    expect(formatTime(null)).toBe('--:--:--');
  });

  it('renders a locale time when date is provided', () => {
    const d = new Date('2026-04-15T10:00:00Z');

    expect(formatTime(d)).toMatch(/\d{1,2}:\d{2}/);
  });
});

describe('formatDateTime', () => {
  it('accepts a Date instance', () => {
    const out = formatDateTime(new Date('2026-04-15T00:00:00Z'));

    expect(out).toEqual(expect.any(String));
    expect(out.length).toBeGreaterThan(0);
  });

  it('accepts an ISO string', () => {
    const out = formatDateTime('2026-04-15T00:00:00Z');

    expect(out).toEqual(expect.any(String));
    expect(out.length).toBeGreaterThan(0);
  });
});

describe('formatDateTimeOrNull', () => {
  it('returns null for undefined', () => {
    expect(formatDateTimeOrNull(undefined)).toBeNull();
  });

  it('returns null for an empty string', () => {
    expect(formatDateTimeOrNull('')).toBeNull();
  });

  it('returns null for an invalid date string', () => {
    expect(formatDateTimeOrNull('not-a-date')).toBeNull();
  });

  it('formats a valid ISO string', () => {
    const out = formatDateTimeOrNull('2026-04-15T12:00:00Z');

    expect(out).toEqual(expect.any(String));
    expect(out).not.toBe('');
  });
});

describe('formatTimeAgo', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-15T12:00:00Z'));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns "just now" for under a minute', () => {
    expect(formatTimeAgo('2026-04-15T11:59:30Z')).toBe('just now');
  });

  it('returns minutes for under an hour', () => {
    expect(formatTimeAgo('2026-04-15T11:30:00Z')).toBe('30m ago');
  });

  it('returns hours for under a day', () => {
    expect(formatTimeAgo('2026-04-15T06:00:00Z')).toBe('6h ago');
  });

  it('returns days for under a week', () => {
    expect(formatTimeAgo('2026-04-12T12:00:00Z')).toBe('3d ago');
  });

  it('falls back to a date string for older than a week', () => {
    const out = formatTimeAgo('2026-03-01T12:00:00Z');

    expect(out).not.toMatch(/ago$/);
    expect(out).toEqual(expect.any(String));
  });
});

describe('formatUptime', () => {
  it('uses minutes only when under an hour', () => {
    expect(formatUptime(60 * 10)).toBe('10m');
  });

  it('uses hours + minutes when under a day', () => {
    expect(formatUptime(60 * 60 * 3 + 60 * 15)).toBe('3h 15m');
  });

  it('uses days + hours + minutes when over a day', () => {
    expect(formatUptime(60 * 60 * 24 * 2 + 60 * 60 * 4 + 60 * 30)).toBe('2d 4h 30m');
  });
});

describe('formatNextRun', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-15T12:00:00Z'));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns the configured unknown label when nextRun is null', () => {
    expect(formatNextRun(null)).toBe('Unknown');
    expect(formatNextRun(null, 'TBD')).toBe('TBD');
  });

  it('returns minutes for under an hour', () => {
    expect(formatNextRun('2026-04-15T12:30:00Z')).toBe('30m');
  });

  it('returns hours for under a day', () => {
    expect(formatNextRun('2026-04-15T15:30:00Z')).toMatch(/h$/);
  });

  it('returns a date string for over a day away', () => {
    const out = formatNextRun('2026-04-17T12:00:00Z');

    expect(out).not.toMatch(/[mh]$/);
  });
});

describe('normalizeTimestamp', () => {
  it('leaves empty input unchanged', () => {
    expect(normalizeTimestamp('')).toBe('');
  });

  it('leaves ISO input unchanged', () => {
    expect(normalizeTimestamp('2026-04-15T12:00:00Z')).toBe('2026-04-15T12:00:00Z');
  });

  it('replaces the first space with T when value lacks T', () => {
    expect(normalizeTimestamp('2026-04-15 12:00:00')).toBe('2026-04-15T12:00:00');
  });

  it('leaves space inside an ISO-marked value unchanged', () => {
    // Has both space and T — function only normalizes the no-T case.
    expect(normalizeTimestamp('2026-04-15T12:00:00 UTC')).toBe('2026-04-15T12:00:00 UTC');
  });
});

describe('formatChartTooltipTime', () => {
  it('falls back to toLocaleString when timeZone is omitted', () => {
    const out = formatChartTooltipTime(1700000000);

    expect(out).toEqual(expect.any(String));
    expect(out.length).toBeGreaterThan(0);
  });

  it('appends `(+0)` suffix for UTC', () => {
    expect(formatChartTooltipTime(1700000000, 'UTC')).toMatch(/\(\+0\)$/);
  });

  it('uses offsetTimeZone for the suffix when provided', () => {
    const out = formatChartTooltipTime(1700000000, 'UTC', { offsetTimeZone: 'Asia/Kolkata' });

    expect(out).toMatch(/\(\+5:30\)$/);
  });

  it('produces a non-empty suffix for a non-zero IANA offset', () => {
    const out = formatChartTooltipTime(1700000000, 'America/New_York');

    expect(out).toMatch(/\(-\d+\)$/);
  });

  it('returns no suffix when offsetTimeZone is empty string', () => {
    const out = formatChartTooltipTime(1700000000, 'UTC', { offsetTimeZone: '' });

    expect(out).not.toMatch(/\([+-]/);
  });
});
