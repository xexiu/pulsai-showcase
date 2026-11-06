import { TIME_AGO, UPTIME_UNITS } from '@/utils/formatters/constants';
import { getCachedDateTimeFormat } from '@/utils/intl-datetime-format-cache';

/**
 * Format date as time string.
 */
export function formatTime(date: Date | null): string {
  if (!date) return '--:--:--';

  return date.toLocaleTimeString();
}

/**
 * Format date as full datetime string.
 */
export function formatDateTime(dateStr: string | Date): string {
  const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr;

  return date.toLocaleString();
}

/**
 * UTC offset label for an IANA zone at an instant, e.g. "(+2)", "(-5)", "(+5:30)".
 * Matches trading_bots-style clarity: wall time is meaningless without which offset.
 */
function formatChartTimezoneOffsetSuffix(unixSeconds: number, timeZone: string): string {
  const date = new Date(unixSeconds * 1000);
  // Cached: called per hover tick via formatChartTooltipTime during crosshair scrub.
  const tzPart =
    getCachedDateTimeFormat('en-US', {
      timeZone,
      timeZoneName: 'longOffset',
    })
      .formatToParts(date)
      .find((p) => p.type === 'timeZoneName')?.value ?? '';
  const normalized = tzPart.replace(/\u2212/g, '-');
  const m = normalized.match(/GMT([+-])(\d{1,2})(?::(\d{2}))?/i);

  if (m) {
    const sign = m[1];
    const h = parseInt(m[2] ?? '0', 10);
    const minRaw = m[3];
    const min = minRaw != null ? parseInt(minRaw, 10) : 0;

    if (min !== 0) {
      return ` (${sign}${h}:${min.toString().padStart(2, '0')})`;
    }

    return ` (${sign}${h})`;
  }

  if (/^GMT$/i.test(normalized.trim()) || /^UTC$/i.test(normalized.trim())) {
    return ' (+0)';
  }

  return '';
}

/** Optional: IANA zone for `(+N)` only when it differs from `timeZone` (LWC timeToTz + UTC wall-clock). */
export type FormatChartTooltipTimeOptions = {
  offsetTimeZone?: string;
};

/**
 * Format Unix seconds for chart tooltip in a specific timezone.
 *
 * Uses en-GB 24h wall time (DD/MM/YYYY, HH:mm) plus explicit offset, e.g. `02:59 (+2)`,
 * so labels match trading_bots / TV-style clarity regardless of browser locale.
 *
 * **LWC intraday:** `timeZone` is often `UTC` (fake-UTC bar times after `timeToTz`); pass
 * `options.offsetTimeZone` = user chart IANA so `(+N)` matches CHART_TIME_DISPLAY_SOT.md.
 */
export function formatChartTooltipTime(
  unixSeconds: number,
  timeZone?: string,
  options?: FormatChartTooltipTimeOptions
): string {
  const date = new Date(unixSeconds * 1000);
  const offsetZone = options?.offsetTimeZone ?? timeZone;

  if (timeZone) {
    const base = date.toLocaleString('en-GB', {
      timeZone,
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });

    const suffix =
      offsetZone != null && offsetZone !== ''
        ? formatChartTimezoneOffsetSuffix(unixSeconds, offsetZone)
        : '';

    return `${base}${suffix}`;
  }

  return date.toLocaleString();
}

/**
 * Format date for display; returns null for missing or invalid input.
 */
export function formatDateTimeOrNull(ts: string | undefined): string | null {
  if (ts == null || ts === '') return null;

  const date = new Date(ts);

  if (Number.isNaN(date.getTime())) return null;

  return date.toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
}

/**
 * Format date as relative time (e.g., "5m ago", "2h ago").
 */
export function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / TIME_AGO.MS_PER_MINUTE);

  if (diffMins < 1) return 'just now';
  if (diffMins < TIME_AGO.MINUTES_PER_HOUR) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / TIME_AGO.MINUTES_PER_HOUR);

  if (diffHours < TIME_AGO.HOURS_PER_DAY) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / TIME_AGO.HOURS_PER_DAY);

  if (diffDays < TIME_AGO.DAYS_PER_WEEK) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

/**
 * Format uptime in seconds to human-readable string.
 */
export function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / UPTIME_UNITS.SECONDS_PER_DAY);
  const hours = Math.floor(
    (seconds % UPTIME_UNITS.SECONDS_PER_DAY) / UPTIME_UNITS.SECONDS_PER_HOUR
  );
  const minutes = Math.floor(
    (seconds % UPTIME_UNITS.SECONDS_PER_HOUR) / UPTIME_UNITS.SECONDS_PER_MINUTE
  );

  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  }

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }

  return `${minutes}m`;
}

/**
 * Format a future timestamp as relative time until next run.
 */
export function formatNextRun(nextRun: string | null, unknownLabel = 'Unknown'): string {
  if (!nextRun) {
    return unknownLabel;
  }

  const date = new Date(nextRun);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffMins = Math.round(diffMs / TIME_AGO.MS_PER_MINUTE);

  if (diffMins < TIME_AGO.MINUTES_PER_HOUR) {
    return `${diffMins}m`;
  }

  const minutesPerDay = TIME_AGO.MINUTES_PER_HOUR * TIME_AGO.HOURS_PER_DAY;

  if (diffMins < minutesPerDay) {
    return `${Math.round(diffMins / TIME_AGO.MINUTES_PER_HOUR)}h`;
  }

  return date.toLocaleDateString();
}

/**
 * Normalize timestamp to ISO format.
 */
export function normalizeTimestamp(ts: string): string {
  if (!ts) return ts;

  return ts.includes(' ') && !ts.includes('T') ? ts.replace(' ', 'T') : ts;
}

/**
 * Format a macro release timestamp for dashboard display.
 *
 * FRED exposes release *dates* as UTC midnight; we format using the UTC calendar
 * (year/month/day) with locale-appropriate labels so the day does not shift when
 * the user is west of UTC (local midnight ISO would show the wrong calendar date).
 */
export function formatMacroReleaseDayDisplay(isoDate: string, locale: string): string {
  const trimmed = isoDate.trim();

  if (trimmed === '') {
    return isoDate;
  }

  const date = new Date(trimmed);

  if (Number.isNaN(date.getTime())) {
    return isoDate;
  }

  return getCachedDateTimeFormat(locale, {
    timeZone: 'UTC',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}
