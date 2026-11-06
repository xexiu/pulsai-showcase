/**
 * ML model feature strings for Plotly hover (categorized, near-zero filtered).
 */

import { FEATURE_CATEGORY_ORDER } from '@/utils/plotly-chart-helpers/constants';

const MF_HOVER_EXPONENT_LARGE = 1_000_000;
const MF_HOVER_TINY = 1e-4;
const MF_HOVER_THOUSAND = 1000;
const MF_HOVER_ONE = 1;

const NEAR_ZERO_THRESHOLD = 1e-8;

/** Compact display for arbitrary model feature scalars (not currency). */
function formatModelFeatureValue(value: number): string {
  if (!Number.isFinite(value)) {
    return '—';
  }

  const a = Math.abs(value);

  if (a >= MF_HOVER_EXPONENT_LARGE || (a > 0 && a < MF_HOVER_TINY)) {
    return value.toExponential(4);
  }

  if (a >= MF_HOVER_THOUSAND) {
    return value.toFixed(2);
  }

  if (a >= MF_HOVER_ONE) {
    return value.toFixed(4);
  }

  return value.toPrecision(4);
}

/** Collect feature keys matching a prefix set, formatted as `key: value` lines. */
function collectCategoryFeatures(
  keys: string[],
  prefixes: readonly string[],
  features: Record<string, number>,
  consumed: Set<string>
): string[] {
  const lines: string[] = [];

  for (const key of keys) {
    if (consumed.has(key)) continue;
    if (!prefixes.some((p) => key.startsWith(p))) continue;

    const val = features[key];

    if (val !== undefined && Math.abs(val) > NEAR_ZERO_THRESHOLD) {
      lines.push(`${key}: ${formatModelFeatureValue(val)}`);
    }

    consumed.add(key);
  }

  return lines;
}

/**
 * Categorized ML feature lines (same ordering and near-zero filter as signal markers).
 * Returns empty string when there are no features or all values are near-zero.
 */
export function buildModelFeaturesCategorizedHoverText(
  features: Record<string, number> | null | undefined
): string {
  if (features == null || Object.keys(features).length === 0) {
    return '';
  }

  const sortedKeys = Object.keys(features).sort();
  const consumed = new Set<string>();
  const parts: string[] = [];

  for (const category of FEATURE_CATEGORY_ORDER) {
    const lines = collectCategoryFeatures(sortedKeys, category.prefixes, features, consumed);

    if (lines.length > 0) {
      parts.push(`<b>${category.label}</b>`);
      parts.push(...lines);
    }
  }

  const otherKeys = sortedKeys.filter((k) => !consumed.has(k));

  if (otherKeys.length > 0) {
    const otherLines: string[] = [];

    for (const key of otherKeys) {
      const val = features[key];

      if (val !== undefined && Math.abs(val) > NEAR_ZERO_THRESHOLD) {
        otherLines.push(`${key}: ${formatModelFeatureValue(val)}`);
      }
    }

    if (otherLines.length > 0) {
      parts.push('<b>Other</b>');
      parts.push(...otherLines);
    }
  }

  if (parts.length === 0) {
    return '';
  }

  return ['<b>Model features</b>', ...parts].join('<br>');
}
