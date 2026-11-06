/**
 * SingleEquityCurve — single-mode equity curve renderer.
 *
 * Behavior: shows empty-state when no points; otherwise feeds Plotly with
 * a single trace built from `buildSingleModeTrace` and layout from
 * `buildSingleModeLayout`. Title falls back to `${symbol} ${timeframe}` when
 * no explicit `title` is provided. A caller-supplied `lineColor` overrides
 * the theme's `colors.equityCurveLine`.
 */

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SingleEquityCurve } from '@/components/molecules/EquityCurveChart/SingleEquityCurve';

vi.mock('@/components/molecules/EquityCurveChart/useEquityChartTheme', () => ({
  useEquityChartTheme: () => ({
    colors: {
      background: '#000',
      paperBackground: '#000',
      gridColor: '#222',
      textColor: '#fff',
      borderColor: '#333',
      equityCurveLine: '#1f77b4',
      equityCurveFillStart: '#1f77b4',
      equityCurveFillEnd: '#1f77b4',
    },
    isDark: false,
  }),
}));

const mockBuildSingleModeTrace = vi.fn();
const mockBuildSingleModeLayout = vi.fn();

vi.mock('@/components/molecules/EquityCurveChart/equityCurvePlotlyBuilders', () => ({
  buildSingleModeTrace: (...args: unknown[]) => mockBuildSingleModeTrace(...args),
  buildSingleModeLayout: (...args: unknown[]) => mockBuildSingleModeLayout(...args),
}));

const mockPlot = vi.fn((props: { layout?: { title?: { text?: string } }; data?: unknown }) => (
  <div data-testid="equity-curve-plot" data-title={props.layout?.title?.text ?? ''} />
));

vi.mock('@/components/molecules/EquityCurveChart/EquityCurvePlot', () => ({
  EquityCurvePlot: (props: {
    layout?: { title?: { text?: string } };
    data?: unknown;
    height?: number;
  }) => mockPlot(props),
}));

vi.mock('@/components/molecules/EquityCurveChart/EquityCurveEmptyState', () => ({
  EquityCurveEmptyState: ({ height }: { height: number }) => (
    <div data-testid="equity-curve-empty" data-height={height} />
  ),
}));

describe('SingleEquityCurve', () => {
  beforeEach(() => {
    mockPlot.mockClear();
    mockBuildSingleModeTrace.mockReset();
    mockBuildSingleModeTrace.mockReturnValue({ name: 'mock-trace' });
    mockBuildSingleModeLayout.mockReset();
    mockBuildSingleModeLayout.mockImplementation(
      (_colors: unknown, opts: { titleText: string }) => ({
        title: { text: opts.titleText },
      })
    );
  });

  it('renders the empty-state placeholder when equity series is empty', () => {
    render(<SingleEquityCurve equity={[]} symbol="BTC/USDT" timeframe="1d" height={180} />);

    expect(screen.getByTestId('equity-curve-empty')).toHaveAttribute('data-height', '180');
    expect(mockBuildSingleModeTrace).not.toHaveBeenCalled();
  });

  it('builds the single trace with the theme equityCurveLine when lineColor is not provided', () => {
    render(
      <SingleEquityCurve
        equity={[
          { timestamp: '2026-04-01', value: 1 },
          { timestamp: '2026-04-02', value: 2 },
        ]}
        symbol="BTC/USDT"
        timeframe="1h"
      />
    );

    expect(mockBuildSingleModeTrace).toHaveBeenCalledTimes(1);
    expect(mockBuildSingleModeTrace).toHaveBeenCalledWith(
      expect.arrayContaining([expect.objectContaining({ timestamp: '2026-04-01' })]),
      '#1f77b4',
      true,
      false
    );
  });

  it('uses caller-supplied lineColor instead of the theme color', () => {
    render(
      <SingleEquityCurve
        equity={[{ timestamp: '2026-04-01', value: 1 }]}
        symbol="ETH/USDT"
        timeframe="1d"
        lineColor="#ff00aa"
        showFill={false}
      />
    );

    expect(mockBuildSingleModeTrace).toHaveBeenCalledWith(
      expect.anything(),
      '#ff00aa',
      false,
      false
    );
  });

  it('falls back to `${symbol} ${timeframe}` for the chart title when title prop is omitted', () => {
    render(
      <SingleEquityCurve
        equity={[{ timestamp: '2026-04-01', value: 1 }]}
        symbol="BTC/USDT"
        timeframe="4h"
      />
    );

    expect(mockBuildSingleModeLayout).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ titleText: 'BTC/USDT 4h', yAxisLabel: 'Equity ($)' })
    );
    expect(screen.getByTestId('equity-curve-plot')).toHaveAttribute('data-title', 'BTC/USDT 4h');
  });

  it('uses explicit title prop when provided and forwards yAxisLabel', () => {
    render(
      <SingleEquityCurve
        equity={[{ timestamp: '2026-04-01', value: 1 }]}
        symbol="BTC/USDT"
        timeframe="1h"
        title="Realized P&L"
        yAxisLabel="USD"
      />
    );

    expect(mockBuildSingleModeLayout).toHaveBeenCalledWith(expect.anything(), {
      titleText: 'Realized P&L',
      yAxisLabel: 'USD',
    });
    expect(screen.getByTestId('equity-curve-plot')).toHaveAttribute('data-title', 'Realized P&L');
  });
});
