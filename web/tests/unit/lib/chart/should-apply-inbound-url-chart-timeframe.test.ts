// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { shouldApplyInboundUrlChartTimeframe } from '@/lib/chart/should-apply-inbound-url-chart-timeframe';

describe('shouldApplyInboundUrlChartTimeframe', () => {
  const defaults = { defaultTimeframe: '1d' as const };

  it('applies when storage is empty', () => {
    expect(
      shouldApplyInboundUrlChartTimeframe({
        urlTimeframe: '4h',
        storedTimeframe: null,
        ...defaults,
      })
    ).toBe(true);
  });

  it('applies when URL TF is an intentional share (differs from storage and default)', () => {
    expect(
      shouldApplyInboundUrlChartTimeframe({
        urlTimeframe: '4h',
        storedTimeframe: '15m',
        ...defaults,
      })
    ).toBe(true);
  });

  it('does not apply when URL matches storage', () => {
    expect(
      shouldApplyInboundUrlChartTimeframe({
        urlTimeframe: '1h',
        storedTimeframe: '1h',
        ...defaults,
      })
    ).toBe(false);
  });

  it('does not apply when URL is the page default but storage differs (stale link)', () => {
    expect(
      shouldApplyInboundUrlChartTimeframe({
        urlTimeframe: '1d',
        storedTimeframe: '1h',
        ...defaults,
      })
    ).toBe(false);
  });
});
