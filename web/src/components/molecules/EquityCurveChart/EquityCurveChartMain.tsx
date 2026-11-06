'use client';

import type { ReactNode } from 'react';

import { ComparisonEquityCurve } from '@/components/molecules/EquityCurveChart/ComparisonEquityCurve';
import { OverlayEquityCurve } from '@/components/molecules/EquityCurveChart/OverlayEquityCurve';
import { SingleEquityCurve } from '@/components/molecules/EquityCurveChart/SingleEquityCurve';
import type { EquityCurveChartProps } from '@/components/molecules/EquityCurveChart/types';

/**
 * EquityCurveChart - Unified equity curve visualization
 */
export function EquityCurveChart(props: EquityCurveChartProps): ReactNode {
  if (props.mode === 'comparison') {
    return <ComparisonEquityCurve {...props} />;
  }
  if (props.mode === 'overlay') {
    return <OverlayEquityCurve {...props} />;
  }

  return <SingleEquityCurve {...props} />;
}
