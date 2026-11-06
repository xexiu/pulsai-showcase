/**
 * LWC timezone conversion — "local time as UTC".
 *
 * Lives in a separate module so the bundler always picks up the current implementation
 * (avoids stale cache showing old canonical toLocaleString version).
 *
 * Converts UTC instant → wall-clock in target zone → UTC timestamp with those components.
 * E.g. 11:00 UTC in Europe/Madrid (12:00 local) → 12:00 UTC.
 */

import { getCachedDateTimeFormat } from '@/utils/intl-datetime-format-cache';

/** Hoisted: the fallback path matched this per call, allocating a RegExp object per bar. */
const TZ_LOCALE_FALLBACK_RE =
  /(\d{1,2})\/(\d{1,2})\/(\d{4}),?\s+(\d{1,2}):(\d{2}):(\d{2})\s*(AM|PM)?/i;

function getLocalComponentsInTz(
  utcSeconds: number,
  timeZone: string
): {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
} {
  const d = new Date(utcSeconds * 1000);
  // Cached: timeToTz runs per bar during candle/volume sync — a fresh formatter per call
  // was the dominant cost. Output is identical to `new Intl.DateTimeFormat('en-CA', …)`.
  const fmt = getCachedDateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const parts = fmt.formatToParts(d);
  const get = (type: string): number =>
    parseInt(parts.find((p) => p.type === type)?.value ?? '0', 10);

  return {
    year: get('year'),
    month: get('month') - 1,
    day: get('day'),
    hour: get('hour'),
    minute: get('minute'),
    second: get('second'),
  };
}

/**
 * Convert UTC seconds to "local time as UTC" for LWC. Uses formatToParts;
 * if no shift occurred for non-UTC zone, falls back to parsing toLocaleString.
 */
export function timeToTz(utcSeconds: number, timeZone: string): number {
  const d = new Date(utcSeconds * 1000);
  let { year, month, day, hour, minute, second } = getLocalComponentsInTz(utcSeconds, timeZone);

  let result = Math.floor(Date.UTC(year, month, day, hour, minute, second, 0) / 1000);

  if (timeZone !== 'UTC' && result === utcSeconds) {
    const localeString = d.toLocaleString('en-US', { timeZone });
    const match = localeString.match(TZ_LOCALE_FALLBACK_RE);

    if (match) {
      const [, m, dayStr, y, h, minStr, secStr, ampm] = match;

      year = parseInt(y!, 10);
      month = parseInt(m!, 10) - 1;
      day = parseInt(dayStr!, 10);
      let hNum = parseInt(h!, 10);

      if (ampm === 'PM' && hNum < 12) hNum += 12;
      if (ampm === 'AM' && hNum === 12) hNum = 0;
      hour = hNum;
      minute = parseInt(minStr!, 10);
      second = parseInt(secStr!, 10);
      result = Math.floor(Date.UTC(year, month, day, hour, minute, second, 0) / 1000);
    }
  }

  return result;
}
