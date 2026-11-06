import { formatUsd2 } from '@/utils/formatters/currency';

/**
 * Format ratio as percentage with 1 decimal place.
 */
export function formatRatioPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format ratio as percentage with 2 decimal places.
 */
export function formatRatioPercent2(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

/**
 * Format hyperparameter/model param with 4 decimal precision.
 */
export function formatParam(value: unknown): string {
  if (typeof value === 'number') {
    return value.toFixed(4);
  }

  return String(value);
}

/**
 * Format delta value with sign and percentage.
 */
export function formatDelta(delta: number, isPercentage: boolean): string {
  const sign = delta >= 0 ? '+' : '';

  if (isPercentage) {
    return `${sign}${(delta * 100).toFixed(2)}%`;
  }

  return `${sign}${delta.toFixed(4)}`;
}

/**
 * Format metric value for display.
 */
export function formatMetricValue(value: number, isPercentage: boolean): string {
  if (isPercentage) {
    return `${(value * 100).toFixed(2)}%`;
  }

  return value.toFixed(4);
}

/**
 * Safely format unknown value as percentage.
 */
export function safeFormatPercent(value: unknown, fallback = '-'): string {
  if (typeof value !== 'number') return fallback;

  return formatRatioPercent2(value);
}

/**
 * Safely format unknown value as number with decimals.
 */
export function safeFormatNumber(value: unknown, decimals = 2, fallback = '-'): string {
  if (typeof value !== 'number') return fallback;

  return value.toFixed(decimals);
}

/**
 * Safely format unknown value as USD.
 */
export function safeFormatUsd(value: unknown, fallback = '-'): string {
  if (typeof value !== 'number') return fallback;

  return formatUsd2(value);
}

/**
 * Check if unknown value is a positive number.
 */
export function isPositiveNumber(value: unknown): boolean {
  return typeof value === 'number' && value > 0;
}
