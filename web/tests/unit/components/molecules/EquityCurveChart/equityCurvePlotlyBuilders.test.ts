/**
 * Behavior tests for Plotly trace/layout builders (no React, no Plotly runtime).
 *
 * WHY: Regressions in x/y extraction or dash mode break charts silently; builders are pure SoT.
 */

import { describe, expect, it } from 'vitest';

import {
  buildComparisonLayout,
  buildComparisonTraces,
  buildOverlayLayout,
  buildOverlayTraces,
  buildSingleModeLayout,
  buildSingleModeTrace,
} from '@/components/molecules/EquityCurveChart/equityCurvePlotlyBuilders';
import type { PlotlyTraceData } from '@/types/plotly-layout';
import type { EquityOverlaySeriesItem } from '@/types/signal-chart';
import type { ThemeColors } from '@/utils/plotly-chart-helpers';

function mockThemeColors(): ThemeColors {
  return {
    paper: '#111',
    plot: '#222',
    grid: '#333',
    line: '#444',
    text: '#eee',
    textMuted: '#aaa',
    bullish: '#0f0',
    bearish: '#f00',
    signal: '#ff0',
    equityCurveLine: 'hsl(271 91% 55%)',
  };
}

describe('buildSingleModeTrace', () => {
  it('maps equity points to x/y and adds fill when showFill is true', () => {
    const equity = [
      { timestamp: '2024-01-01T00:00:00Z', value: 10_000 },
      { timestamp: '2024-01-02T00:00:00Z', value: 10_100 },
    ];
    const trace = buildSingleModeTrace(equity, '#a855f7', true, true);

    expect(trace['x']).toEqual(['2024-01-01T00:00:00Z', '2024-01-02T00:00:00Z']);
    expect(trace['y']).toEqual([10_000, 10_100]);
    expect(trace['fill']).toBe('tozeroy');
    expect(String(trace['fillcolor'])).toContain('0.1');
  });

  it('uses lighter fill when not dark theme', () => {
    const trace = buildSingleModeTrace([{ timestamp: 't', value: 1 }], '#fff', true, false);

    expect(String(trace['fillcolor'])).toContain('0.15');
  });

  it('sets fill none when showFill is false', () => {
    const trace = buildSingleModeTrace([{ timestamp: 't', value: 1 }], '#fff', false, true);

    expect(trace['fill']).toBe('none');
  });
});

describe('buildSingleModeLayout', () => {
  it('embeds title and uses theme colors on axes', () => {
    const layout = buildSingleModeLayout(mockThemeColors(), {
      titleText: 'BTC 1h',
      yAxisLabel: 'Equity ($)',
    });

    expect((layout['title'] as { text: string }).text).toBe('BTC 1h');
    expect(layout['showlegend']).toBe(false);
    expect((layout['yaxis'] as { tickformat: string }).tickformat).toBe('$,.0f');
  });
});

describe('buildComparisonTraces', () => {
  it('produces two traces with strategy names in hovertemplate', () => {
    const curves = [
      { timestamp: 't1', equity_a: 1, equity_b: 2 },
      { timestamp: 't2', equity_a: 3, equity_b: 4 },
    ];
    const traces = buildComparisonTraces(curves, 'A', 'B', '#00f', '#f0f');

    expect(traces).toHaveLength(2);
    expect((traces[0] as PlotlyTraceData)['name']).toBe('A');
    expect((traces[1] as PlotlyTraceData)['y']).toEqual([2, 4]);
  });
});

describe('buildOverlayTraces', () => {
  it('maps dash solid vs dash for Plotly line.dash', () => {
    const series: EquityOverlaySeriesItem[] = [
      {
        name: 'S',
        points: [{ timestamp: 't', value: 1 }],
        color: '#111',
        dash: 'solid',
      },
      {
        name: 'B',
        points: [{ timestamp: 't', value: 2 }],
        color: '#222',
        dash: 'dash',
      },
    ];
    const traces = buildOverlayTraces(series);
    const line0 = traces[0]?.['line'] as { dash: string } | undefined;
    const line1 = traces[1]?.['line'] as { dash: string } | undefined;

    expect(line0?.dash).toBe('solid');
    expect(line1?.dash).toBe('dash');
  });
});

describe('buildOverlayLayout', () => {
  it('uses higher top margin than comparison layout for legend clearance', () => {
    const overlay = buildOverlayLayout(mockThemeColors(), {
      chartTitle: 'T',
      yAxisLabel: 'Y',
    });
    const comparison = buildComparisonLayout(mockThemeColors(), {
      chartTitle: 'T',
      yAxisLabel: 'Y',
    });
    const overlayMargin = overlay['margin'] as { t: number };
    const comparisonMargin = comparison['margin'] as { t: number };

    expect(overlayMargin.t).toBeGreaterThan(comparisonMargin.t);
  });
});
