/**
 * Property-based tests for the parsers that take input from outside the app: backend timestamps and API error bodies.
 *
 * IMPORTERS/CALLERS: vitest (`property-tests/**`). AFFECTED API: none. DATA SCHEMAS: none.
 *
 * Kept outside `tests/` because that folder is regenerated from the monorepo on every export.
 */
import fc from 'fast-check';
import { describe, expect, it } from 'vitest';

import { timestampToChartTime } from '@/utils/chart-timestamp';
import { parseApiErrorDetail } from '@/utils/parseApiErrorBody';

const FALLBACK = 'fallback message';
const BODY_PREFIX = 'body: ';
/** 2001-09-09 to 2100-01-01: seconds whose millisecond form is above the "treat as ms" threshold. */
const unixSeconds = fc.integer({ min: 1_000_000_000, max: 4_102_444_800 });
const nonEmptyText = fc.string({ minLength: 1 });

describe('timestampToChartTime', () => {
  it('reads the same instant from seconds, milliseconds and an ISO string', () => {
    fc.assert(
      fc.property(unixSeconds, fc.integer({ min: 0, max: 999 }), (seconds, millis) => {
        const milliseconds = seconds * 1000 + millis;

        expect(timestampToChartTime(seconds)).toBe(seconds);
        expect(timestampToChartTime(milliseconds)).toBe(seconds);
        expect(timestampToChartTime(new Date(milliseconds).toISOString())).toBe(seconds);
      }),
    );
  });

  it('answers any input with whole seconds or NaN, and never throws', () => {
    fc.assert(
      fc.property(fc.anything(), (input) => {
        const chartTime = timestampToChartTime(input);

        expect(Number.isNaN(chartTime) || Number.isInteger(chartTime)).toBe(true);
      }),
    );
  });
});

describe('parseApiErrorDetail', () => {
  it('answers any parsed body with a string, and never throws', () => {
    fc.assert(
      fc.property(fc.anything(), (body) => {
        expect(typeof parseApiErrorDetail(body, FALLBACK)).toBe('string');
      }),
    );
  });

  it('returns the fallback for anything that is not an object', () => {
    const notAnObject = fc.oneof(fc.string(), fc.double(), fc.boolean(), fc.constant(null), fc.constant(undefined));

    fc.assert(
      fc.property(notAnObject, (body) => {
        expect(parseApiErrorDetail(body, FALLBACK)).toBe(FALLBACK);
      }),
    );
  });

  it('prefers the middleware message over a FastAPI detail', () => {
    const message = nonEmptyText.filter((text) => !text.startsWith(BODY_PREFIX));

    fc.assert(
      fc.property(message, nonEmptyText, (errorMessage, detail) => {
        expect(parseApiErrorDetail({ error: { message: errorMessage }, detail }, FALLBACK)).toBe(errorMessage);
      }),
    );
  });

  it('strips the middleware prefix from a validation message', () => {
    fc.assert(
      fc.property(fc.string(), (text) => {
        expect(parseApiErrorDetail({ error: { message: `${BODY_PREFIX}${text}` } }, FALLBACK)).toBe(text.trim());
      }),
    );
  });
});
