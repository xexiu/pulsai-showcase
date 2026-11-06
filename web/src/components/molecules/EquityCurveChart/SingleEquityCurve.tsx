'use client';

import type { ReactNode } from 'react';

import { EquityCurveEmptyState } from '@/components/molecules/EquityCurveChart/EquityCurveEmptyState';
import { EquityCurvePlot } from '@/components/molecules/EquityCurveChart/EquityCurvePlot';
import {
  buildSingleModeLayout,
  buildSingleModeTrace,
} from '@/components/molecules/EquityCurveChart/equityCurvePlotlyBuilders';
import type { SingleModeProps } from '@/components/molecules/EquityCurveChart/types';
import { useEquityChartTheme } from '@/components/molecules/EquityCurveChart/useEquityChartTheme';

export function SingleEquityCurve({
  equity,
  symbol,
  timeframe,
  height = 250,
  yAxisLabel = 'Equity ($)',
  title,
  lineColor,
  showFill = true,
}: SingleModeProps): ReactNode {
  const { colors, isDark } = useEquityChartTheme();

  if (equity.length === 0) {
    return <EquityCurveEmptyState height={height} />;
  }

  const strokeColor = lineColor ?? colors.equityCurveLine;
  const trace = buildSingleModeTrace(equity, strokeColor, showFill, isDark);
  const titleText = title ?? `${symbol} ${timeframe}`;
  const layout = buildSingleModeLayout(colors, { titleText, yAxisLabel });

  return (
    <EquityCurvePlot
      data={[trace]}
      layout={layout}
      config={{ displayModeBar: false, responsive: true }}
      height={height}
    />
  );
}
