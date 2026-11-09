import type { ReactNode } from 'react';

import { getDynamicVolatilityRegimeDotClass } from '@/utils/plotly-chart-helpers';

export type DynamicRegimeLegendProps = {
  show: boolean;
  activeRegimes: Array<'low' | 'mid' | 'high'>;
  label: string;
  regimeLabels?: Partial<Record<'low' | 'mid' | 'high', string>>;
};

export function DynamicRegimeLegend({
  show,
  activeRegimes,
  label,
  regimeLabels,
}: DynamicRegimeLegendProps): ReactNode {
  if (!show || activeRegimes.length === 0) {
    return null;
  }

  return (
    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span>{label}</span>
      {activeRegimes.map((regime) => (
        <span key={regime} className="inline-flex items-center gap-1 rounded border px-2 py-0.5">
          <span
            className={`inline-block h-2 w-2 rounded-full ${getDynamicVolatilityRegimeDotClass(regime)}`}
          />
          {regimeLabels?.[regime] ?? regime}
        </span>
      ))}
    </div>
  );
}
