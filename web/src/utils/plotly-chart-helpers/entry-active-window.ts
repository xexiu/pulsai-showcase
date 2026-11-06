import type { SignalData } from '@/utils/plotly-chart-helpers/types';
import { mapTimestampForPlotlyTrace, type PlotlyTimeOptions } from '@/utils/plotly-chart-time';

export type EntryActiveWindowInput = {
  timestamp: string;
  side?: 'long' | 'short';
};

export type EntryActiveWindow = {
  x0: number;
  x1: number;
};

export function resolveEntryActiveWindow(
  entry: EntryActiveWindowInput,
  signals: SignalData[],
  plotlyTime: PlotlyTimeOptions,
  fallbackEndTimestamp?: string
): EntryActiveWindow {
  const exitSignal = signals.find(
    (signal) =>
      signal.type === 'EXIT' &&
      signal.timestamp > entry.timestamp &&
      (entry.side == null || signal.side === entry.side)
  );

  return {
    x0: mapTimestampForPlotlyTrace(entry.timestamp, plotlyTime),
    x1: mapTimestampForPlotlyTrace(
      exitSignal?.timestamp ?? fallbackEndTimestamp ?? entry.timestamp,
      plotlyTime
    ),
  };
}
