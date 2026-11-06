// =============================================================================
// Chart Timezone — SoT for chart timezone read/write and LWC localization
// =============================================================================
//
// WHY THIS FILE?
// - Chart axis IANA: localStorage override, else Intl auto-detect; server `chart_timezone` may
//   seed localStorage once when empty (see chart-timezone-seed + CHART_TIME_DISPLAY_SOT.md).
// - Axis (LWC timeFormatter) and tooltip use the same IANA zone via useChartTimezonePreference.
// - IANA names only; DST handled by Intl.
//
// @see docs/04-structural/CHART_TIME_DISPLAY_SOT.md
// @see docs/02-technical/SIGNAL_CANDLE_TIMEZONE_ARCHITECTURE.md
// =============================================================================

import { shouldChartBarTimesUseLegacyTimeToTz } from '@pulsai/shared';

import { timeToTz } from '@/utils/chart-timezone-convert';
import { STORAGE_KEYS } from '@/utils/constants';
import { getCachedDateTimeFormat } from '@/utils/intl-datetime-format-cache';

export { timeToTz };

/** Safe default when window is undefined (SSR). Matches common fallback in docs. */
const SSR_DEFAULT_TIMEZONE = 'UTC';

/**
 * Whether to apply `timeToTz` ("local wall clock as UTC") to bar times before LWC `setData`.
 *
 * **SoT:** `shouldChartBarTimesUseLegacyTimeToTz` in `@pulsai/shared` (same semantics).
 * Policy lives next to `TIMEFRAME_CONFIG` and `CHART_BAR_RAW_UTC_MIN_MINUTES` — not inside `timeToTz` (pure transform).
 *
 * @param timeframe - Chart TF (e.g. `1h`, `4h`, `1d`). Unknown TFs keep legacy behavior (apply).
 */
export function shouldApplyTimeToTzForTimeframe(timeframe: string | undefined): boolean {
  return shouldChartBarTimesUseLegacyTimeToTz(timeframe);
}

/**
 * Map a bar open (UTC seconds) to the same x-scale as lightweight-charts (`timeToTz` when legacy TFs).
 *
 * Used by Plotly backtest charts so candle/signal x aligns with the dashboard chart for the same preference.
 */
export function mapUtcBarOpenSecondsForChartDisplay(
  utcSeconds: number,
  chartTimezone: string,
  timeframe: string | undefined
): number {
  if (!shouldApplyTimeToTzForTimeframe(timeframe)) {
    return utcSeconds;
  }

  return timeToTz(utcSeconds, chartTimezone);
}

/**
 * IANA zone for LWC `localization.timeFormatter` so axis labels match how bar `time` is encoded.
 * - Legacy bar encoding + timeToTz on bars → formatter must stay UTC (fake UTC).
 * - Raw UTC bars (4h+ per shared) → formatter uses the user's chart timezone.
 */
export function getChartTimeAxisFormatterZone(
  chartTimezone: string,
  timeframe: string | undefined
): string {
  return shouldApplyTimeToTzForTimeframe(timeframe) ? 'UTC' : chartTimezone;
}

/**
 * Read chart timezone: user preference from localStorage, or browser auto-detect.
 *
 * WHY SSR-safe? Next.js can render on server; window/localStorage is undefined there.
 * Returns UTC so server never reads localStorage and no hydration mismatch (client
 * will re-run and get real value).
 *
 * @returns IANA timezone string (e.g. 'Europe/Madrid'). Never null/undefined.
 */
export function getChartTimezone(): string {
  if (typeof window === 'undefined') {
    return SSR_DEFAULT_TIMEZONE;
  }

  const stored = window.localStorage.getItem(STORAGE_KEYS.CHART_TIMEZONE);

  if (stored != null && stored !== '') {
    return stored;
  }

  if (
    typeof Intl !== 'undefined' &&
    Intl.DateTimeFormat?.prototype?.resolvedOptions != null &&
    Intl.DateTimeFormat().resolvedOptions != null
  ) {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  }

  return SSR_DEFAULT_TIMEZONE;
}

/**
 * Persist chart timezone preference. Call when user selects a new zone from dropdown.
 *
 * WHY SSR no-op? Same as getChartTimezone; avoid errors during SSR.
 * WHY catch and ignore? Quota/security errors are rare; failing the UI is worse than not persisting.
 *
 * @param ianaName - IANA timezone name (e.g. 'Europe/Madrid'). Not validated; caller must pass valid IANA.
 */
export function setChartTimezone(ianaName: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEYS.CHART_TIMEZONE, ianaName);
  } catch {
    // Intentional no-op: quota/security errors are rare; failing the UI is worse than not persisting.
  }
}

/**
 * Options object for chart.applyOptions({ localization: ... }).
 * Lightweight-charts expects timeFormatter(utcSeconds) for the time scale.
 */
export type ChartLocalizationOptions = {
  localization: {
    timeFormatter: (utcSeconds: number) => string;
  };
};

/**
 * Build localization options for lightweight-charts so axis (time scale) labels use the given IANA zone.
 * Same zone as tooltip — chart bar labels and tooltip time stay in sync.
 *
 * LWC has no built-in timezone option; we pass a custom timeFormatter so UTC data is displayed in the chosen zone.
 *
 * @param ianaName - IANA timezone (e.g. 'Europe/Madrid')
 * @returns Options to pass to chart.applyOptions({ localization: { timeFormatter } }).
 */
export function buildChartLocalizationOptions(ianaName: string): ChartLocalizationOptions {
  const locale = typeof navigator !== 'undefined' && navigator.language ? navigator.language : 'en';

  // LWC calls `timeFormatter` per visible bar on every scroll/zoom. Resolve the formatter
  // once here (cached by locale+zone) instead of constructing one inside the closure.
  const axisFormatter = getCachedDateTimeFormat(locale, {
    timeZone: ianaName,
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });

  return {
    localization: {
      timeFormatter: (utcSeconds: number): string =>
        axisFormatter.format(new Date(utcSeconds * 1000)),
    },
  };
}
