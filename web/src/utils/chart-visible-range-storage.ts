/**
 * Persist lightweight-charts viewport (pan/zoom + manual price scale) to localStorage — PoC.
 *
 * WHY logical + time:
 * - `setVisibleRange(time)` cannot reproduce scroll with right-side whitespace; the library
 *   clamps to bar times. Pan/zoom state is best captured as `getVisibleLogicalRange()` /
 *   `setVisibleLogicalRange()` (see official time-scale docs + GitHub discussions).
 * - We still store time as fallback for older saved keys.
 *
 * WHY price (Y-axis zoom):
 * - Time-scale subscriptions do not fire when the user only drags the right price axis.
 *   `IPriceScaleApi.getVisibleRange` / `setVisibleRange` capture manual vertical zoom; we
 *   persist that separately and restore after data + time viewport restore.
 *
 * @see https://tradingview.github.io/lightweight-charts/docs/time-scale
 * @see https://tradingview.github.io/lightweight-charts/docs/api/interfaces/IPriceScaleApi
 * @see useChartVisibleRangePersistence
 */

import { ENABLED_TIMEFRAMES } from '@pulsai/shared';

import { STORAGE_KEYS } from '@/utils/constants';

/** SoT: same prefix as STORAGE_KEYS.CHART_VISIBLE_RANGE_V1_PREFIX */
const CHART_VISIBLE_RANGE_STORAGE_PREFIX = STORAGE_KEYS.CHART_VISIBLE_RANGE_V1_PREFIX;

/** v2: logical + optional time + optional manual price range (main series price scale) */
export type StoredChartViewport = {
  logical?: { from: number; to: number };
  time?: { from: number; to: number };
  price?: { from: number; to: number };
};

export function buildChartVisibleRangeStorageKey(
  variant: 'dashboard' | 'full',
  symbol: string,
  timeframe: string,
  storageScope?: string
): string {
  const scopedSuffix = storageScope == null || storageScope.trim() === '' ? '' : `:${storageScope}`;

  return `${CHART_VISIBLE_RANGE_STORAGE_PREFIX}${variant}:${symbol}:${timeframe}${scopedSuffix}`;
}

/**
 * Stable per-chart identity string used as a ``chartKey`` for fitContent
 * gating, sync-effect data-key prefixes, and viewport scoping.
 *
 * Was inlined as ``\`${symbol}-${timeframe}\`` at 5+ call sites
 * (``tradingChartUnifiedSyncOptions``, ``candle-apply``,
 * ``live-candle-sync-context``, ``useRefetchOhlcvWhenRealtimeDisconnected``,
 * ``useRealtimeCandles``, …). Centralised so a future change (e.g. namespace
 * by exchange) propagates through one place.
 */
export function buildChartIdentityKey(symbol: string, timeframe: string): string {
  return `${symbol}-${timeframe}`;
}

/** Inverse of {@link buildChartIdentityKey} for known {@link ENABLED_TIMEFRAMES} suffixes. */
export function parseChartIdentityKey(
  chartKey: string
): { symbol: string; timeframe: string } | null {
  for (const timeframe of ENABLED_TIMEFRAMES) {
    const suffix = `-${timeframe}`;

    if (!chartKey.endsWith(suffix)) {
      continue;
    }

    const symbol = chartKey.slice(0, -suffix.length);

    if (symbol.length === 0) {
      return null;
    }

    return { symbol, timeframe };
  }

  return null;
}

/** True when only the timeframe segment of a chart identity key changed (same symbol). */
export function isChartIdentityTimeframeOnlyChange(previousKey: string, nextKey: string): boolean {
  const previous = parseChartIdentityKey(previousKey);
  const next = parseChartIdentityKey(nextKey);

  if (previous == null || next == null) {
    return false;
  }

  return previous.symbol === next.symbol && previous.timeframe !== next.timeframe;
}

/**
 * Whether a saved pan/zoom snapshot still matches the loaded bar count.
 *
 * After TF switch, refetch, or longer history, an old logical range can point past the
 * series end — LWC then shows wide empty bands that look like missing candles.
 */
export function isStoredViewportCompatibleWithBarCount(
  stored: StoredChartViewport,
  barCount: number
): boolean {
  if (barCount <= 0) {
    return false;
  }

  const lastIndex = barCount - 1;

  if (stored.logical != null) {
    const { from, to } = stored.logical;

    if (to < 0 || from > lastIndex) {
      return false;
    }

    if (from >= barCount) {
      return false;
    }

    // Logical ``to`` past the last bar paints empty bands (looks like missing OHLCV).
    if (to > lastIndex) {
      return false;
    }

    return true;
  }

  if (stored.time != null) {
    return true;
  }

  return false;
}

export function loadStoredViewport(storageKey: string): StoredChartViewport | null {
  if (typeof window === 'undefined') return null;

  try {
    const raw = window.localStorage.getItem(storageKey);

    if (raw == null || raw === '') return null;

    const parsed = JSON.parse(raw) as unknown;

    return normalizeViewport(parsed);
  } catch {
    return null;
  }
}

export function saveStoredViewport(storageKey: string, viewport: StoredChartViewport): void {
  if (typeof window === 'undefined') return;

  try {
    const { logical, time, price } = viewport;

    if (logical != null && logical.from >= logical.to) return;

    if (time != null && time.from >= time.to) return;

    if (price != null && price.from >= price.to) return;

    if (logical == null && time == null && price == null) return;

    window.localStorage.setItem(storageKey, JSON.stringify(viewport));
  } catch {
    /* quota / private mode — ignore */
  }
}

function readNestedPair(
  o: Record<string, unknown>,
  key: string
): { from: number; to: number } | undefined {
  const v = o[key];

  if (!isPair(v) || !isFinitePair(v as Record<string, unknown>)) return undefined;

  const r = v as Record<string, unknown>;

  return { from: r['from'] as number, to: r['to'] as number };
}

function isValidAscendingPair(p: { from: number; to: number }): boolean {
  return p.from < p.to;
}

function validateViewport(out: StoredChartViewport): StoredChartViewport | null {
  if (out.logical != null && !isValidAscendingPair(out.logical)) return null;

  if (out.time != null && !isValidAscendingPair(out.time)) return null;

  if (out.price != null && !isValidAscendingPair(out.price)) return null;

  if (out.logical == null && out.time == null && out.price == null) return null;

  return out;
}

function normalizeViewport(value: unknown): StoredChartViewport | null {
  if (value == null || typeof value !== 'object') return null;

  const o = value as Record<string, unknown>;
  const out: StoredChartViewport = {};

  const logical = readNestedPair(o, 'logical');

  if (logical != null) {
    out.logical = logical;
  }

  const time = readNestedPair(o, 'time');

  if (time != null) {
    out.time = time;
  }

  const price = readNestedPair(o, 'price');

  if (price != null) {
    out.price = price;
  }

  if (out.logical == null && out.time == null && isPair(o) && isFinitePair(o)) {
    out.time = { from: o['from'] as number, to: o['to'] as number };
  }

  return validateViewport(out);
}

function isPair(v: unknown): v is Record<string, unknown> {
  if (v == null || typeof v !== 'object') return false;

  const r = v as Record<string, unknown>;

  return 'from' in r && 'to' in r;
}

function isFinitePair(r: Record<string, unknown>): boolean {
  return (
    typeof r['from'] === 'number' &&
    typeof r['to'] === 'number' &&
    Number.isFinite(r['from']) &&
    Number.isFinite(r['to'])
  );
}
