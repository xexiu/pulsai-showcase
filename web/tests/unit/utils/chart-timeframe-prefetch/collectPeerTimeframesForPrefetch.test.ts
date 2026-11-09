// @vitest-environment node
/**
 * The peer the user is about to click must be first in the queue, not last.
 *
 * OWNER: "cause all must be prefetch for fast loading when user lands and when user clicks on
 * other timeframes!!"
 *
 * The prefetch already covered every allowed peer, so coverage was never the gap. The SCHEDULE
 * was. On the full chart peers are warmed SERIALLY — `prefetchMaxConcurrent: 1`, 400 ms stagger,
 * after a 2 s delay (`chartDataPolicy.defaults.ts`). Eleven peers is therefore a queue about ten
 * seconds long, and in registry order the last slot went to `1w` while the user sitting on `1h`
 * clicks `30m` or `4h` — which were behind nine other requests.
 *
 * Ordering by distance from the active timeframe costs nothing (same set, same concurrency) and
 * moves the likely next click from the back of the queue to the front: roughly 2.4 s instead of
 * up to 10 s.
 *
 * @see apps/web/src/config/chart-data-policy/chartDataPolicy.defaults.ts
 */

import { describe, expect, it } from 'vitest';

import type { Timeframe } from '@/types/chart';
import { collectPeerTimeframesForPrefetch } from '@/utils/chart-timeframe-prefetch/collectPeerTimeframesForPrefetch';

/** Registry order, as the chart offers them. */
const ALLOWED = ['5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w'] as unknown as Timeframe[];

describe('collectPeerTimeframesForPrefetch', () => {
  it('still returns every allowed peer, and never the active one', () => {
    // Coverage is the property that must NOT change: reordering must not drop a timeframe.
    const peers = collectPeerTimeframesForPrefetch(ALLOWED, '1h' as Timeframe);

    expect(peers).toHaveLength(ALLOWED.length - 1);
    expect(peers).not.toContain('1h');
    expect([...peers].sort()).toEqual([...ALLOWED].filter((tf) => tf !== '1h').sort());
  });

  it('puts the adjacent timeframes first, because that is what gets clicked', () => {
    // THE DEFECT: in registry order this returned 5m,15m,30m,2h,4h,1d,1w — so 30m and 2h, the
    // two most likely next clicks from 1h, sat at positions 3 and 4 of a serial queue.
    const peers = collectPeerTimeframesForPrefetch(ALLOWED, '1h' as Timeframe);

    expect(peers.slice(0, 2)).toEqual(['30m', '2h']);
  });

  it('orders strictly by distance from the active timeframe', () => {
    const peers = collectPeerTimeframesForPrefetch(ALLOWED, '1h' as Timeframe);

    expect(peers).toEqual(['30m', '2h', '15m', '4h', '5m', '1d', '1w']);
  });

  it('breaks ties toward the shorter timeframe, deterministically', () => {
    // `Array.prototype.sort` is stable per spec, so equal distances keep registry order. Pinned
    // because "whichever comes out" is not a schedule anyone can reason about.
    const peers = collectPeerTimeframesForPrefetch(ALLOWED, '1h' as Timeframe);
    const below = peers.indexOf('30m' as Timeframe);
    const above = peers.indexOf('2h' as Timeframe);

    expect(below).toBeLessThan(above);
  });

  it('handles the active timeframe at an edge of the list', () => {
    const peers = collectPeerTimeframesForPrefetch(ALLOWED, '5m' as Timeframe);

    expect(peers).toEqual(['15m', '30m', '1h', '2h', '4h', '1d', '1w']);
  });

  it('returns the set untouched when the active timeframe is not allowed', () => {
    // No position to measure distance from; ordering against a phantom index would be arbitrary.
    const peers = collectPeerTimeframesForPrefetch(ALLOWED, '3d' as Timeframe);

    expect(peers).toEqual(ALLOWED);
  });

  it('returns nothing when the allowed list is empty', () => {
    // Carried over from the previous version of this file. Rewriting a test module is how
    // coverage silently disappears, so the cases it already pinned are kept rather than assumed
    // to be implied by the new ones.
    expect(collectPeerTimeframesForPrefetch([], '1h' as Timeframe)).toEqual([]);
  });

  it('returns nothing when the active timeframe is the only one allowed', () => {
    expect(
      collectPeerTimeframesForPrefetch(['1h'] as unknown as Timeframe[], '1h' as Timeframe)
    ).toEqual([]);
  });

  it('does not mutate the caller list', () => {
    // It sorts the filtered copy, not the input — an in-place sort here would reorder the
    // caller's allowed-timeframes array, which drives the timeframe selector's button order.
    const allowed = [...ALLOWED];

    collectPeerTimeframesForPrefetch(allowed, '1h' as Timeframe);

    expect(allowed).toEqual(ALLOWED);
  });
});
