'use client';

import type { ReactNode } from 'react';

import { EquityCurveEmptyState } from '@/components/molecules/EquityCurveChart/EquityCurveEmptyState';
import { EquityCurvePlot } from '@/components/molecules/EquityCurveChart/EquityCurvePlot';
import {
  buildComparisonLayout,
  buildComparisonTraces,
  PLOTLY_MODE_BAR_REMOVE,
} from '@/components/molecules/EquityCurveChart/equityCurvePlotlyBuilders';
import type { ComparisonModeProps } from '@/components/molecules/EquityCurveChart/types';
import { useEquityChartTheme } from '@/components/molecules/EquityCurveChart/useEquityChartTheme';

export function ComparisonEquityCurve({
  equityCurves,
  strategyAName,
  strategyBName,
  symbol,
  timeframe,
  height = 400,
  yAxisLabel = 'Equity ($)',
  title,
  strategyAColor = '#3b82f6',
  strategyBColor = '#a855f7',
}: ComparisonModeProps): ReactNode {
  const { colors } = useEquityChartTheme();

  if (equityCurves.length === 0) {
    return <EquityCurveEmptyState height={height} />;
  }

  const data = buildComparisonTraces(
    equityCurves,
    strategyAName,
    strategyBName,
    strategyAColor,
    strategyBColor
  );
  const chartTitle = title ?? `${symbol} ${timeframe}`;
  const layout = buildComparisonLayout(colors, { chartTitle, yAxisLabel });

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
