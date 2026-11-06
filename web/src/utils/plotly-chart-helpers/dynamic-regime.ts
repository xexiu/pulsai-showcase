import type { ThemeColors } from '@/utils/plotly-chart-helpers/types';

export type DynamicVolatilityRegime = 'low' | 'mid' | 'high';

export const DYNAMIC_VOLATILITY_REGIME_ORDER: DynamicVolatilityRegime[] = ['low', 'mid', 'high'];

export function getDynamicVolatilityRegimeColor(
  regime: DynamicVolatilityRegime,
  colors: ThemeColors
): string {
  if (regime === 'low') {
    return colors.bullish;
  }
  if (regime === 'high') {
    return colors.bearish;
  }

  return colors.signal;
}

export function getDynamicVolatilityRegimeDotClass(regime: DynamicVolatilityRegime): string {
  if (regime === 'low') {
    return 'bg-emerald-500';
  }
  if (regime === 'high') {
    return 'bg-red-500';
  }

  return 'bg-amber-500';
}

export function toDynamicVolatilityRegime(value: unknown): DynamicVolatilityRegime | null {
  if (typeof value !== 'string') {
    return null;
  }
  const lowered = value.toLowerCase();

  if (lowered === 'low' || lowered === 'mid' || lowered === 'high') {
    return lowered;
  }

  return null;
}
