import type { Timeframe } from '@/types/chart';

/**
 * Peer timeframes to warm in TanStack cache: all allowed except the active one, NEAREST FIRST.
 *
 * WHY THE ORDER MATTERS, and why it is not cosmetic. The full chart warms peers SERIALLY —
 * `prefetchMaxConcurrent: 1` with a 400 ms stagger after a 2 s delay
 * (`chartDataPolicy.defaults.ts`). With 11 peers that queue runs for roughly ten seconds, so
 * whichever timeframe sits last is cold for ten seconds after landing. In registry order that
 * last slot goes to `1w` — but a user on `1h` almost always clicks `30m` or `4h` next, and those
 * were sitting behind nine other requests.
 *
 * Sorting by distance from the active timeframe puts the likely next click at the FRONT of the
 * queue: adjacent peers are warm in about 2.4 s instead of up to 10 s. The serial schedule is
 * left alone deliberately — it exists so peer warming does not compete with the chart the user
 * is actually looking at, and 11 peers can be several MB. This changes the ORDER only, so it
 * cannot add load: the same set is fetched, and the cheap win is taken first.
 *
 * Ties keep registry order because `Array.prototype.sort` is stable (spec since ES2019), so a
 * peer one step below the active timeframe is fetched before the one a step above it.
 */
export function collectPeerTimeframesForPrefetch(
  allowedTimeframes: readonly Timeframe[],
  activeTimeframe: Timeframe
): Timeframe[] {
  const peers = allowedTimeframes.filter((tf) => tf !== activeTimeframe);
  const activeIndex = allowedTimeframes.indexOf(activeTimeframe);

  if (activeIndex < 0) {
    // The active timeframe is not in the allowed list — there is no "near" to sort by, so the
    // set is returned untouched rather than ordered against a position that does not exist.
    return peers;
  }

  return peers.sort(
    (left, right) =>
      Math.abs(allowedTimeframes.indexOf(left) - activeIndex) -
      Math.abs(allowedTimeframes.indexOf(right) - activeIndex)
  );
}
