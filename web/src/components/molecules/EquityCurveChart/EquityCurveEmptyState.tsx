'use client';

import type { ReactNode } from 'react';

import { useTranslations } from 'next-intl';

export interface EquityCurveEmptyStateProps {
  height: number;
}

export function EquityCurveEmptyState({ height }: EquityCurveEmptyStateProps): ReactNode {
  const t = useTranslations('admin.training');

  return (
    <div
      className="flex items-center justify-center text-gray-500 dark:text-gray-400"
      style={{ height }}
    >
      {t('noEquityData')}
    </div>
  );
}
