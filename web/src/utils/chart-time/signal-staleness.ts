// =============================================================================
// Signal staleness — SoT for "is this signal still fresh?"
// =============================================================================
//
// Previously inlined in AISignalDisplay; promoted to chart-time SoT so the
// dashboard header, banner, and any future consumer all share one rule and
// one threshold.
//
// Rule: a signal is stale when its age exceeds SIGNAL_STALE_THRESHOLD_MULTIPLIER
// times its own timeframe (e.g. 5m signal older than 7.5 min → stale).
// =============================================================================

import { getTimeframeMs } from '@/utils/chart-time/countdown';

export const SIGNAL_STALE_THRESHOLD_MULTIPLIER = 1.5;

interface StalenessSignal {
  timestamp: string;
  timeframe: string;
}

/**
 * True when a signal's age exceeds the staleness threshold for its timeframe.
 *
 * Returns `false` for `null`, missing timestamp, unknown timeframe, and
 * future-dated timestamps — all "we can't conclude stale, so don't claim it".
 *
 * @param signal - The signal to evaluate, or `null` when none is available.
 * @param nowMs - Optional clock override (defaults to `Date.now()`); kept for tests.
 */
export function isSignalStale(signal: StalenessSignal | null, nowMs?: number): boolean {
  if (signal === null) return false;
  if (!signal.timestamp) return false;

  const tfMs = getTimeframeMs(signal.timeframe);

  if (tfMs === null) return false;

  const now = nowMs ?? Date.now();
  const ageMs = now - new Date(signal.timestamp).getTime();

  if (ageMs < 0) return false;

  return ageMs > tfMs * SIGNAL_STALE_THRESHOLD_MULTIPLIER;
}
