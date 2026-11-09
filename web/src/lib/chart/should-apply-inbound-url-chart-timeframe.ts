import type { Timeframe } from '@/types/chart';

export type ShouldApplyInboundUrlChartTimeframeInput = {
  urlTimeframe: Timeframe;
  storedTimeframe: string | null;
  defaultTimeframe: Timeframe;
};

/**
 * Whether the full-chart URL `?timeframe=` should override localStorage on first visit.
 *
 * - Empty storage → always apply URL.
 * - URL matches storage → no write (preference already aligned).
 * - URL equals page default (e.g. stale `1d` in an old link) while storage differs → keep storage.
 * - URL differs from storage and is not the page default → inbound share; apply once per session.
 */
export function shouldApplyInboundUrlChartTimeframe(
  input: ShouldApplyInboundUrlChartTimeframeInput
): boolean {
  const { urlTimeframe, storedTimeframe, defaultTimeframe } = input;

  if (storedTimeframe == null) {
    return true;
  }

  if (urlTimeframe === storedTimeframe) {
    return false;
  }

  if (urlTimeframe === defaultTimeframe) {
    return false;
  }

  return true;
}
