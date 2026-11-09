// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { formatMacroReleaseDayDisplay } from '@/utils/formatters/datetime';

describe('formatMacroReleaseDayDisplay', () => {
  it('formats FRED-style UTC midnight as locale date without shifting calendar day', () => {
    const iso = '2026-04-15T00:00:00+00:00';
    const formatted = formatMacroReleaseDayDisplay(iso, 'en-US');

    expect(formatted).toMatch(/2026/);
    expect(formatted).toMatch(/15/);
    expect(formatted).toMatch(/Apr/i);
    expect(formatted).not.toContain('T');
    expect(formatted).not.toContain('+00:00');
  });

  it('uses UTC calendar components so US evening does not show prior local calendar day', () => {
    const iso = '2026-06-20T00:00:00+00:00';
    const us = formatMacroReleaseDayDisplay(iso, 'en-US');

    expect(us).toContain('20');
    expect(us).toContain('2026');
  });

  it('respects locale for month naming', () => {
    const iso = '2026-03-01T00:00:00+00:00';
    const en = formatMacroReleaseDayDisplay(iso, 'en-US');
    const es = formatMacroReleaseDayDisplay(iso, 'es');

    expect(en.toLowerCase()).toContain('mar');
    expect(es).not.toBe(en);
  });

  it('returns original string when input is not a valid date', () => {
    const bad = 'not-an-iso-date';

    expect(formatMacroReleaseDayDisplay(bad, 'en-US')).toBe(bad);
  });
});
