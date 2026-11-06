'use client';

import type { ReactNode } from 'react';

import dynamic from 'next/dynamic';

import type { PlotlyConfig, PlotlyLayout, PlotlyTraceData } from '@/types/plotly-layout';

import type { PlotParams } from 'react-plotly.js';

const Plot = dynamic(() => import('@/components/molecules/BacktestChart/PlotlyWrapper'), {
  ssr: false,
  loading: (): ReactNode => <div className="h-64 animate-pulse bg-gray-200 dark:bg-gray-800" />,
});

export interface EquityCurvePlotProps {
  data: PlotlyTraceData[];
  layout: PlotlyLayout;
  config: PlotlyConfig;
  height: number;
}

/**
 * Shared Plotly wrapper for equity charts (SSR off, resize handler on).
 */
export function EquityCurvePlot({ data, layout, config, height }: EquityCurvePlotProps): ReactNode {
  return (
    <Plot
      data={data as PlotParams['data']}
      layout={layout as PlotParams['layout']}
      config={config as PlotParams['config']}
      style={{ width: '100%', height }}
      useResizeHandler
    />
  );
}
