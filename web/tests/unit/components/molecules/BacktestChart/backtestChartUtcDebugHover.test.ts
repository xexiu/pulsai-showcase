import { describe, expect, it } from 'vitest';

import { buildBacktestUtcDebugHoverText } from '@/components/molecules/BacktestChart/backtestChartUtcDebugHover';

describe('buildBacktestUtcDebugHoverText', () => {
  it('embeds raw BE ml fields without reformatting confidence', () => {
    const c = {
      timestamp: '2026-04-12T18:55:00+00:00',
      open: 100,
      high: 110,
      low: 95,
      close: 105,
      ml_prediction: 'BUY' as const,
      ml_confidence_percent: 71.926,
    };

    const ht = buildBacktestUtcDebugHoverText(c, true);

    expect(ht).toContain('BE timestamp: 2026-04-12T18:55:00+00:00');
    expect(ht).toContain('BE ml_prediction: BUY');
    expect(ht).toContain('BE ml_confidence_percent: 71.926');
    expect(ht).toContain('Single candlestick trace');
  });

  it('omits ML block when chartMlModelHover is false', () => {
    const c = {
      timestamp: '2026-04-12T18:55:00+00:00',
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      ml_prediction: 'HOLD' as const,
      ml_confidence_percent: 42,
    };

    const ht = buildBacktestUtcDebugHoverText(c, false);

    expect(ht).not.toContain('BE ml_prediction');
    expect(ht).not.toContain('BE ml_confidence_percent');
  });

  it('does not include P0 parity lines when indicator_groups.p0_exact is set', () => {
    const c = {
      timestamp: '2026-04-12T18:55:00+00:00',
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      indicator_groups: { p0_exact: { rsi_14: 40.1 } },
    };

    const ht = buildBacktestUtcDebugHoverText(c, false);

    expect(ht).not.toContain('P0 indicators (parity)');
    expect(ht).not.toContain('rsi_14');
  });

  it('does not include P4 chart-pattern parity lines when indicator_groups.p4_chart_pattern is set', () => {
    const c = {
      timestamp: '2026-04-12T18:55:00+00:00',
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      indicator_groups: { p4_chart_pattern: { cp_support_line: 0.99 } },
    };

    const ht = buildBacktestUtcDebugHoverText(c, false);

    expect(ht).not.toContain('P4 chart-pattern (parity)');
    expect(ht).not.toContain('cp_support_line');
  });

  it('does not include P1 alias parity lines when indicator_groups.p1_alias is set', () => {
    const c = {
      timestamp: '2026-04-12T18:55:00+00:00',
      open: 1,
      high: 2,
      low: 0.5,
      close: 1.5,
      indicator_groups: { p1_alias: { support_pa_20: 95.2 } },
    };

    const ht = buildBacktestUtcDebugHoverText(c, false);

    expect(ht).not.toContain('P1 aliases (parity)');
    expect(ht).not.toContain('support_pa_20');
  });
});
