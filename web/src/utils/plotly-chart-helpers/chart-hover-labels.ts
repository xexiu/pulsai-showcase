import { formatPrice } from '@/utils/formatters';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';

const HOVER_LINE_BREAK = '<br>';

export type ChartHoverLabels = {
  confidence: string;
  entryFee: string;
  exitReason: string;
  exitNetPnl: string;
  exitFee: string;
  stopLoss: string;
  takeProfit: string;
  dcaFill: string;
  long: string;
  short: string;
};

const DEFAULT_CHART_HOVER_LABELS: ChartHoverLabels = {
  confidence: 'Confidence:',
  entryFee: 'Entry Fee:',
  exitReason: 'Reason:',
  exitNetPnl: 'Net PnL:',
  exitFee: 'Exit Fee:',
  stopLoss: 'Stop Loss:',
  takeProfit: 'Take Profit:',
  dcaFill: 'DCA fill',
  long: 'Long',
  short: 'Short',
};

export function buildSignalEntryHoverText(
  signal: SignalData,
  type: 'BUY' | 'SELL',
  executionNote: string,
  labels: ChartHoverLabels = DEFAULT_CHART_HOVER_LABELS
): string {
  const parts: string[] = [`${type} @ ${formatPrice(signal.price)}`, executionNote];

  if (signal.confidence !== undefined) {
    parts.push(`${labels.confidence} ${signal.confidence.toFixed(1)}%`);
  }
  if (signal.entry_fee !== undefined) {
    parts.push(`${labels.entryFee} ${formatPrice(signal.entry_fee)}`);
  }

  return parts.join(HOVER_LINE_BREAK);
}

export function buildCompoundFillHoverText(
  signal: SignalData,
  labels: ChartHoverLabels = DEFAULT_CHART_HOVER_LABELS
): string {
  const direction = signal.type === 'BUY' ? labels.long : labels.short;
  const parts: string[] = [`${labels.dcaFill} (${direction}) @ ${formatPrice(signal.price)}`];

  if (signal.confidence !== undefined) {
    parts.push(`${labels.confidence} ${signal.confidence.toFixed(1)}%`);
  }

  return parts.join(HOVER_LINE_BREAK);
}

export function buildSignalExitHoverText(
  signal: SignalData,
  labels: ChartHoverLabels = DEFAULT_CHART_HOVER_LABELS
): string {
  const parts: string[] = [`EXIT @ ${formatPrice(signal.price)}`];

  if (signal.reason) parts.push(`${labels.exitReason} ${signal.reason}`);
  if (signal.net_pnl !== undefined)
    parts.push(`${labels.exitNetPnl} ${formatPrice(signal.net_pnl)}`);
  if (signal.exit_fee !== undefined)
    parts.push(`${labels.exitFee} ${formatPrice(signal.exit_fee)}`);
  if (signal.stop_loss !== undefined)
    parts.push(`${labels.stopLoss} ${formatPrice(signal.stop_loss)}`);
  if (signal.take_profit !== undefined) {
    parts.push(`${labels.takeProfit} ${formatPrice(signal.take_profit)}`);
  }

  return parts.join(HOVER_LINE_BREAK);
}
