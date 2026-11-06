/**
 * EquityCurveChart props (aliases chart SoT types for backward-compatible imports).
 */

import type { EquityOverlaySeriesItem, SignalChartEquityPoint } from '@/types/signal-chart';

export type { EquityOverlaySeriesItem, SignalChartEquityPoint as EquityPoint };

/** Aligned equity points for comparison (two strategies). */
export interface EquityPointComparison {
  timestamp: string;
  equity_a: number;
  equity_b: number;
}

interface BaseEquityChartProps {
  symbol: string;
  timeframe: string;
  height?: number;
  yAxisLabel?: string;
  title?: string;
}

export interface SingleModeProps extends BaseEquityChartProps {
  mode?: 'single';
  equity: SignalChartEquityPoint[];
  lineColor?: string;
  showFill?: boolean;
}

export interface ComparisonModeProps extends BaseEquityChartProps {
  mode: 'comparison';
  equityCurves: EquityPointComparison[];
  strategyAName: string;
  strategyBName: string;
  strategyAColor?: string;
  strategyBColor?: string;
}

export interface OverlayModeProps extends BaseEquityChartProps {
  mode: 'overlay';
  series: EquityOverlaySeriesItem[];
}

export type EquityCurveChartProps = SingleModeProps | ComparisonModeProps | OverlayModeProps;
