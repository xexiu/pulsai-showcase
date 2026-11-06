import { formatPrice } from '@/utils/formatters';
import { buildModelFeaturesCategorizedHoverText } from '@/utils/plotly-chart-helpers/model-features-hover';
import type { SignalData } from '@/utils/plotly-chart-helpers/types';

/**
 * Categorized ML feature hover for BUY/SELL signal markers.
 * Groups features by prefix into ordered sections, filters zero/near-zero values.
 * Falls back to basic signal info when no features available.
 */
export function buildSignalMlHoverText(
  signal: Pick<SignalData, 'type' | 'price' | 'confidence'>,
  features: Record<string, number> | null | undefined
): string {
  const header = `<b>${signal.type} @ ${formatPrice(signal.price)}</b>`;
  const parts: string[] = [header];

  if (signal.confidence != null && Number.isFinite(signal.confidence)) {
    parts.push(`Confidence: ${signal.confidence.toFixed(1)}%`);
  }

  const mfBlock = buildModelFeaturesCategorizedHoverText(features);

  if (mfBlock) {
    parts.push(mfBlock);
  }

  return parts.join('<br>');
}
