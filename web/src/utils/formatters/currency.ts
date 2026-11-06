import { DECIMAL_PLACES, FORMAT_THRESHOLDS } from '@/utils/formatters/constants';

/**
 * Format number as price with currency symbol.
 */
export function formatPrice(value: number, currency: string = '$', decimals: number = 2): string {
  const formatted = value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return `${currency}${formatted}`;
}

/**
 * Format number as percentage.
 */
export function formatPercent(
  value: number,
  decimals: number = 2,
  showSign: boolean = true
): string {
  const sign = showSign && value >= 0 ? '+' : '';

  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format large numbers with abbreviations.
 */
export function formatCompact(value: number): string {
  if (value >= FORMAT_THRESHOLDS.BILLION) {
    return `${(value / FORMAT_THRESHOLDS.BILLION).toFixed(1)}B`;
  }
  if (value >= FORMAT_THRESHOLDS.MILLION) {
    return `${(value / FORMAT_THRESHOLDS.MILLION).toFixed(1)}M`;
  }
  if (value >= FORMAT_THRESHOLDS.THOUSAND) {
    return `${(value / FORMAT_THRESHOLDS.THOUSAND).toFixed(1)}K`;
  }

  return value.toString();
}

/**
 * Format crypto price with appropriate decimals based on magnitude.
 */
export function formatCryptoPrice(price: number): string {
  if (price >= FORMAT_THRESHOLDS.THOUSAND) {
    return price.toLocaleString('en-US', {
      minimumFractionDigits: DECIMAL_PLACES.DEFAULT,
      maximumFractionDigits: DECIMAL_PLACES.DEFAULT,
    });
  }
  if (price >= 1) {
    return price.toFixed(DECIMAL_PLACES.CRYPTO_MEDIUM);
  }

  return price.toFixed(DECIMAL_PLACES.CRYPTO_PRECISE);
}

/**
 * Format volume with K/M/B suffixes and 2 decimal places.
 */
export function formatVolume(volume: number): string {
  if (volume >= FORMAT_THRESHOLDS.BILLION) {
    return `${(volume / FORMAT_THRESHOLDS.BILLION).toFixed(DECIMAL_PLACES.DEFAULT)}B`;
  }
  if (volume >= FORMAT_THRESHOLDS.MILLION) {
    return `${(volume / FORMAT_THRESHOLDS.MILLION).toFixed(DECIMAL_PLACES.DEFAULT)}M`;
  }
  if (volume >= FORMAT_THRESHOLDS.THOUSAND) {
    return `${(volume / FORMAT_THRESHOLDS.THOUSAND).toFixed(DECIMAL_PLACES.DEFAULT)}K`;
  }

  return volume.toFixed(DECIMAL_PLACES.DEFAULT);
}

/**
 * Format number as USD with locale formatting.
 */
export function formatUsd(value: number): string {
  return `$${value.toLocaleString('en-US')}`;
}

/**
 * Format number as USD with 2 decimal places.
 */
export function formatUsd2(value: number): string {
  return `$${value.toFixed(2)}`;
}

/**
 * Signed USD for P&amp;L-style lines (e.g. price bar): `+$12.34` / `-$12.34` / `+$0.00`.
 */
export function formatSignedUsd2(value: number): string {
  const abs = Math.abs(value);
  const core = abs.toFixed(2);

  if (value < 0) {
    return `-$${core}`;
  }

  return `+$${core}`;
}
