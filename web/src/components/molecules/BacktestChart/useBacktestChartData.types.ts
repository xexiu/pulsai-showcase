import type {
  Candle,
  EquityPoint,
  Prediction,
  Signal,
} from '@/components/molecules/BacktestChart/types';
import type { PlotlyConfig, PlotlyLayout } from '@/types/plotly-layout';
import type { PlotlyShape } from '@/utils/plotly-chart-helpers';
import type { ChartHoverLabels } from '@/utils/plotly-chart-helpers/chart-hover-labels';
import type {
  BBData,
  MACDData,
  PlotlyData,
  RSIData,
  ThemeColors,
} from '@/utils/plotly-chart-helpers/types';
import type { PlotlyTimeOptions } from '@/utils/plotly-chart-time';

interface BacktestChartLabels {
  noData: string;
  dynamicRegimeTraceNamePrefix: string;
  dynamicRegimeHoverEntryPrefix: string;
  dynamicRegimeHoverRegimeLabel: string;
  dynamicRegimeLabelLow: string;
  dynamicRegimeLabelMid: string;
  dynamicRegimeLabelHigh: string;
  hoverConfidence: string;
  hoverEntryFee: string;
  hoverExitReason: string;
  hoverExitNetPnl: string;
  hoverExitFee: string;
  hoverStopLoss: string;
  hoverTakeProfit: string;
  hoverDcaFill: string;
  hoverLong: string;
  hoverShort: string;
}

export interface UseBacktestChartDataProps {
  candles: Candle[];
  signals: Signal[];
  predictions?: Prediction[];
  equityCurve?: EquityPoint[];
  symbol: string;
  timeframe: string;
  showEquityCurve: boolean;
  isDark?: boolean;
  rsi?: RSIData | undefined;
  macd?: MACDData | undefined;
  bollingerBands?: BBData | undefined;
  chartMlModelHover?: boolean;
  chartDisplayTimezone?: string;
  showRLevelGuides?: boolean;
  showLiquidationGuides?: boolean;
  showLiquidationHeatmap?: boolean;
  showDynamicRegimeHints?: boolean;
  chartHeight?: number;
  chartLabels: BacktestChartLabels;
}

export interface UseBacktestChartDataReturn {
  data: PlotlyData[];
  layout: PlotlyLayout;
  config: PlotlyConfig;
}

export type BuildTracesInput = {
  candles: Candle[];
  signals: Signal[];
  predictions: Prediction[] | undefined;
  equityCurve: EquityPoint[] | undefined;
  showEquityCurve: boolean;
  colors: ThemeColors;
  plotlyTime: PlotlyTimeOptions;
  rsi: RSIData | undefined;
  macd: MACDData | undefined;
  bollingerBands: BBData | undefined;
  hasRSI: boolean;
  hasMACD: boolean;
  chartMlModelHover: boolean;
  showDynamicRegimeHints: boolean;
  chartLabels: BacktestChartLabels;
};

export type BacktestLayoutInput = {
  symbol: string;
  timeframe: string;
  showEquityCurve: boolean;
  hasRSI: boolean;
  hasMACD: boolean;
  colors: ThemeColors;
  chartDisplayTimezone: string | undefined;
  chartHeight: number | undefined;
  tpSlShapes: PlotlyShape[];
  rGuideShapes: PlotlyShape[];
  liquidationGuideShapes: PlotlyShape[];
  liquidationHeatmapShapes: PlotlyShape[];
};

export type UseBacktestChartLayoutParams = {
  candles: Candle[];
  signals: Signal[];
  symbol: string;
  timeframe: string;
  showEquityCurve: boolean;
  hasRSI: boolean;
  hasMACD: boolean;
  colors: ThemeColors;
  chartDisplayTimezone: string | undefined;
  chartHeight: number | undefined;
  showRLevelGuides: boolean;
  showLiquidationGuides: boolean;
  showLiquidationHeatmap: boolean;
};

export type BuildHoverLabelsInput = BacktestChartLabels;

export type BuildHoverLabelsOutput = ChartHoverLabels;
