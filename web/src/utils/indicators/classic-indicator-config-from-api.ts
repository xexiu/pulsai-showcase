import type { ClassicIndicatorConfig } from '@/types/classic-indicator-config';

export type ClassicIndicatorConfigOptions = {
  rsiPeriod?: number;
  macdFastPeriod?: number;
  macdSlowPeriod?: number;
  macdSignalPeriod?: number;
  bbPeriod?: number;
  bbStdDev?: number;
};

/**
 * Map BE classic_indicator_config into useIndicators option overrides.
 * Dashboard/trade only — full chart uses BE series directly.
 */
export function classicIndicatorConfigToOptions(
  config: ClassicIndicatorConfig | undefined
): ClassicIndicatorConfigOptions {
  if (config == null) {
    return {};
  }

  return {
    rsiPeriod: config.rsi_period,
    macdFastPeriod: config.macd_fast,
    macdSlowPeriod: config.macd_slow,
    macdSignalPeriod: config.macd_signal,
    bbPeriod: config.bb_period,
    bbStdDev: config.bb_std,
  };
}
