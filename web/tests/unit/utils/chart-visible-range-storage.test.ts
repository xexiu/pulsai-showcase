// @vitest-environment jsdom
/**
 * chart-visible-range-storage.ts — identity helpers AND the localStorage half.
 *
 * ENVIRONMENT CHANGED node → jsdom (2026-08-29). `loadStoredViewport` / `saveStoredViewport`
 * short-circuit on `typeof window === 'undefined'`, so under the node environment they returned
 * early and every validation branch below them was unreachable. The pure helpers already here do
 * not care which environment they run in, so extending this file beats a second one — vitest
 * pins the environment per FILE, and one module deserves one test file.
 *
 * WHY: measured 2026-08-29, this module carried 34 uncovered branches, the second-largest branch
 * deficit in the FE report while the gate failed at 83.92% branches against an 85% threshold.
 * Branches, not statements, are the binding constraint, and the validation guards are where they
 * live.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildChartIdentityKey,
  buildChartVisibleRangeStorageKey,
  isChartIdentityTimeframeOnlyChange,
  isStoredViewportCompatibleWithBarCount,
  loadStoredViewport,
  parseChartIdentityKey,
  saveStoredViewport,
  type StoredChartViewport,
} from '@/utils/chart-visible-range-storage';

const KEY = 'test:viewport';

beforeEach(() => {
  window.localStorage.clear();
  vi.restoreAllMocks();
});

describe('parseChartIdentityKey', () => {
  it('round-trips buildChartIdentityKey for slash symbols', () => {
    const key = buildChartIdentityKey('BTC/USDT', '4h');

    expect(parseChartIdentityKey(key)).toEqual({ symbol: 'BTC/USDT', timeframe: '4h' });
  });
});

describe('isChartIdentityTimeframeOnlyChange', () => {
  it('is true for same symbol different timeframe', () => {
    expect(
      isChartIdentityTimeframeOnlyChange(
        buildChartIdentityKey('BTC/USDT', '1h'),
        buildChartIdentityKey('BTC/USDT', '4h')
      )
    ).toBe(true);
  });

  it('is false when symbol changes', () => {
    expect(
      isChartIdentityTimeframeOnlyChange(
        buildChartIdentityKey('BTC/USDT', '4h'),
        buildChartIdentityKey('ETH/USDT', '4h')
      )
    ).toBe(false);
  });
});

describe('isStoredViewportCompatibleWithBarCount', () => {
  it('rejects logical range extending past the last bar index', () => {
    const stored: StoredChartViewport = {
      logical: { from: 0, to: 900 },
    };

    expect(isStoredViewportCompatibleWithBarCount(stored, 838)).toBe(false);
  });

  it('accepts logical range ending on the last bar', () => {
    const stored: StoredChartViewport = {
      logical: { from: 700, to: 837 },
    };

    expect(isStoredViewportCompatibleWithBarCount(stored, 838)).toBe(true);
  });

  it('rejects any viewport when no bars are loaded', () => {
    expect(isStoredViewportCompatibleWithBarCount({ logical: { from: 0, to: 1 } }, 0)).toBe(false);
  });

  it('rejects a logical range entirely before the series', () => {
    expect(isStoredViewportCompatibleWithBarCount({ logical: { from: -20, to: -1 } }, 100)).toBe(
      false
    );
  });

  it('rejects a logical range starting past the last bar', () => {
    expect(isStoredViewportCompatibleWithBarCount({ logical: { from: 200, to: 300 } }, 100)).toBe(
      false
    );
  });

  it('accepts a time-only viewport, which carries no bar index to invalidate', () => {
    expect(isStoredViewportCompatibleWithBarCount({ time: { from: 1, to: 2 } }, 100)).toBe(true);
  });

  it('rejects a viewport with neither logical nor time', () => {
    expect(isStoredViewportCompatibleWithBarCount({ price: { from: 1, to: 2 } }, 100)).toBe(false);
  });
});

describe('parseChartIdentityKey — rejections', () => {
  it('returns null when no known timeframe suffix matches', () => {
    expect(parseChartIdentityKey('BTCUSDT-99y')).toBeNull();
  });

  it('returns null when the symbol half is empty', () => {
    expect(parseChartIdentityKey('-4h')).toBeNull();
  });
});

describe('isChartIdentityTimeframeOnlyChange — unparseable keys', () => {
  it('is false when the previous key cannot be parsed', () => {
    expect(
      isChartIdentityTimeframeOnlyChange('garbage', buildChartIdentityKey('BTC/USDT', '4h'))
    ).toBe(false);
  });

  it('is false when the next key cannot be parsed', () => {
    expect(
      isChartIdentityTimeframeOnlyChange(buildChartIdentityKey('BTC/USDT', '4h'), 'garbage')
    ).toBe(false);
  });

  it('is false when nothing changed', () => {
    const key = buildChartIdentityKey('BTC/USDT', '4h');

    expect(isChartIdentityTimeframeOnlyChange(key, key)).toBe(false);
  });
});

describe('buildChartVisibleRangeStorageKey — the scope suffix is optional', () => {
  it('omits the suffix when no scope is given', () => {
    expect(buildChartVisibleRangeStorageKey('dashboard', 'BTCUSDT', '4h')).toContain(
      'dashboard:BTCUSDT:4h'
    );
  });

  it('treats an empty scope as no scope', () => {
    expect(buildChartVisibleRangeStorageKey('full', 'BTCUSDT', '4h', '')).toBe(
      buildChartVisibleRangeStorageKey('full', 'BTCUSDT', '4h')
    );
  });

  it('treats a whitespace-only scope as no scope', () => {
    // The guard is `.trim() === ''`. A bare falsiness check would append ':   ' and split one
    // chart's saved viewport across two keys.
    expect(buildChartVisibleRangeStorageKey('full', 'BTCUSDT', '4h', '   ')).toBe(
      buildChartVisibleRangeStorageKey('full', 'BTCUSDT', '4h')
    );
  });

  it('appends a real scope', () => {
    expect(buildChartVisibleRangeStorageKey('full', 'BTCUSDT', '4h', 'compare')).toContain(
      ':compare'
    );
  });

  it('keeps the two chart variants apart', () => {
    expect(buildChartVisibleRangeStorageKey('dashboard', 'BTCUSDT', '4h')).not.toBe(
      buildChartVisibleRangeStorageKey('full', 'BTCUSDT', '4h')
    );
  });
});

describe('saveStoredViewport — refuses viewports that would paint wrong', () => {
  it('round-trips a valid logical range', () => {
    saveStoredViewport(KEY, { logical: { from: 0, to: 100 } });

    expect(loadStoredViewport(KEY)).toEqual({ logical: { from: 0, to: 100 } });
  });

  it.each([
    ['logical', { logical: { from: 100, to: 100 } }],
    ['time', { time: { from: 5, to: 1 } }],
    ['price', { price: { from: 9, to: 9 } }],
  ])('drops a non-ascending %s pair', (_label, viewport) => {
    saveStoredViewport(KEY, viewport as StoredChartViewport);

    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it('writes nothing when every field is absent', () => {
    saveStoredViewport(KEY, {});

    expect(window.localStorage.getItem(KEY)).toBeNull();
  });

  it('swallows a storage failure instead of throwing into the render', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    expect(() => saveStoredViewport(KEY, { logical: { from: 0, to: 10 } })).not.toThrow();
  });
});

describe('loadStoredViewport — never throws, returns null instead', () => {
  it('returns null for a missing key', () => {
    expect(loadStoredViewport('absent')).toBeNull();
  });

  it('returns null for an empty string', () => {
    window.localStorage.setItem(KEY, '');

    expect(loadStoredViewport(KEY)).toBeNull();
  });

  it('returns null for unparseable JSON', () => {
    window.localStorage.setItem(KEY, '{not json');

    expect(loadStoredViewport(KEY)).toBeNull();
  });

  it('returns null for a JSON primitive', () => {
    window.localStorage.setItem(KEY, '42');

    expect(loadStoredViewport(KEY)).toBeNull();
  });

  it('returns null for JSON null', () => {
    window.localStorage.setItem(KEY, 'null');

    expect(loadStoredViewport(KEY)).toBeNull();
  });

  it('reads a legacy FLAT {from,to} as a time range', () => {
    // v1 keys stored the time pair at the top level. Dropping them would silently reset every
    // returning user's viewport, which is why the fallback exists.
    window.localStorage.setItem(KEY, JSON.stringify({ from: 1000, to: 2000 }));

    expect(loadStoredViewport(KEY)).toEqual({ time: { from: 1000, to: 2000 } });
  });

  it('rejects a non-finite pair rather than restoring NaN', () => {
    window.localStorage.setItem(KEY, JSON.stringify({ logical: { from: 0, to: null } }));

    expect(loadStoredViewport(KEY)).toBeNull();
  });

  it('rejects a pair whose members are strings', () => {
    window.localStorage.setItem(KEY, JSON.stringify({ logical: { from: '0', to: '10' } }));

    expect(loadStoredViewport(KEY)).toBeNull();
  });

  it('drops a stored object carrying neither from nor to', () => {
    window.localStorage.setItem(KEY, JSON.stringify({ nothing: true }));

    expect(loadStoredViewport(KEY)).toBeNull();
  });

  it('rejects a descending logical range that reached storage', () => {
    window.localStorage.setItem(KEY, JSON.stringify({ logical: { from: 50, to: 10 } }));

    expect(loadStoredViewport(KEY)).toBeNull();
  });

  it('keeps every recognised section together', () => {
    const viewport: StoredChartViewport = {
      logical: { from: 0, to: 10 },
      time: { from: 100, to: 200 },
      price: { from: 1, to: 2 },
    };

    window.localStorage.setItem(KEY, JSON.stringify(viewport));

    expect(loadStoredViewport(KEY)).toEqual(viewport);
  });

  it('keeps a price-only viewport, which is manual Y-axis zoom with no pan', () => {
    window.localStorage.setItem(KEY, JSON.stringify({ price: { from: 10, to: 20 } }));

    expect(loadStoredViewport(KEY)).toEqual({ price: { from: 10, to: 20 } });
  });
});
