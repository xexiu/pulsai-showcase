'use client';

import type { ReactNode } from 'react';

import { EquityCurveEmptyState } from '@/components/molecules/EquityCurveChart/EquityCurveEmptyState';
import { EquityCurvePlot } from '@/components/molecules/EquityCurveChart/EquityCurvePlot';
import {
  buildOverlayLayout,
  buildOverlayTraces,
  PLOTLY_MODE_BAR_REMOVE,
} from '@/components/molecules/EquityCurveChart/equityCurvePlotlyBuilders';
import type {
  EquityOverlaySeriesItem,
  OverlayModeProps,
} from '@/components/molecules/EquityCurveChart/types';
import { useEquityChartTheme } from '@/components/molecules/EquityCurveChart/useEquityChartTheme';

function filterNonEmptySeries(series: EquityOverlaySeriesItem[]): EquityOverlaySeriesItem[] {
  return series.filter((s) => s.points.length > 0);
}

export function OverlayEquityCurve({
  series,
  symbol,
  timeframe,
  height = 320,
  yAxisLabel = 'Equity ($)',
  title,
}: OverlayModeProps): ReactNode {
  const { colors } = useEquityChartTheme();

  const valid = filterNonEmptySeries(series);

  if (valid.length === 0) {
    return <EquityCurveEmptyState height={height} />;
  }

  const data = buildOverlayTraces(valid);
  const chartTitle = title ?? `${symbol} ${timeframe}`;
  const layout = buildOverlayLayout(colors, { chartTitle, yAxisLabel });

  return (
    <EquityCurvePlot
      data={data}
      layout={layout}
      config={{
        displayModeBar: true,
        modeBarButtonsToRemove: PLOTLY_MODE_BAR_REMOVE,
        displaylogo: false,
        responsive: true,
      }}
      height={height}
    />
  );
}
