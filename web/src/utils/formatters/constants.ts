/** Numeric thresholds for compact formatting */
export const FORMAT_THRESHOLDS = {
  BILLION: 1_000_000_000,
  MILLION: 1_000_000,
  THOUSAND: 1_000,
} as const;

/** Decimal places for various price formats */
export const DECIMAL_PLACES = {
  CRYPTO_PRECISE: 8,
  CRYPTO_MEDIUM: 4,
  DEFAULT: 2,
} as const;

/** Time constants for formatTimeAgo / formatNextRun */
export const TIME_AGO = {
  MS_PER_MINUTE: 60000,
  MINUTES_PER_HOUR: 60,
  HOURS_PER_DAY: 24,
  DAYS_PER_WEEK: 7,
} as const;

/** Time constants for formatUptime (in seconds) */
export const UPTIME_UNITS = {
  SECONDS_PER_MINUTE: 60,
  SECONDS_PER_HOUR: 3600,
  SECONDS_PER_DAY: 86400,
} as const;
