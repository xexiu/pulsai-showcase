'use client';

/**
 * MetricComparisonRow - Displays a metric comparison between two model versions.
 *
 * WHY as a Molecule:
 * - Combines multiple text elements into a comparison row
 * - Reusable for any metric comparison scenario
 * - Follows SRP: displays one metric comparison
 */

import type { ReactNode } from 'react';

import { formatDelta as formatDeltaUtil, formatMetricValue } from '@/utils/formatters';

export interface MetricComparisonRowProps {
  metric: string;
  valueA: number | undefined | null;
  valueB: number | undefined | null;
  delta: number | undefined | null;
  versionA: number;
  versionB: number;
}

function formatValue(value: number | undefined | null, isPercentage: boolean): string {
  if (value === undefined || value === null) {
    return 'N/A';
  }

  return formatMetricValue(value, isPercentage);
}

function formatDelta(delta: number | undefined | null, isPercentage: boolean): string {
  if (delta === undefined || delta === null) {
    return 'N/A';
  }

  return formatDeltaUtil(delta, isPercentage);
}

/**
 * Get color class based on delta value.
 * Green for positive, red for negative, gray for neutral/N/A.
 */
function getDeltaColor(delta: number | undefined | null): string {
  if (delta === undefined || delta === null) {
    return 'text-gray-500 dark:text-gray-400';
  }
  if (delta > 0) {
    return 'text-green-600 dark:text-green-400';
  }
  if (delta < 0) {
    return 'text-red-600 dark:text-red-400';
  }

  return 'text-gray-500 dark:text-gray-400';
}

export function MetricComparisonRow({
  metric,
  valueA,
  valueB,
  delta,
  versionA,
  versionB,
}: MetricComparisonRowProps): ReactNode {
  const isPercentage = metric.includes('accuracy') || metric.includes('score');
  const deltaColor = getDeltaColor(delta);

  return (
    <div className="flex items-center justify-between px-6 py-4">
      <span className="font-medium capitalize text-gray-900 dark:text-white">
        {metric.replace(/_/g, ' ')}
      </span>
      <div className="flex items-center gap-8">
        <div className="text-right">
          <span className="text-xs text-gray-500 dark:text-gray-400">v{versionA}</span>
          <p className="font-mono text-gray-900 dark:text-white">
            {formatValue(valueA, isPercentage)}
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs text-gray-500 dark:text-gray-400">v{versionB}</span>
          <p className="font-mono text-gray-900 dark:text-white">
            {formatValue(valueB, isPercentage)}
          </p>
        </div>
        <div className={`text-right font-mono font-medium ${deltaColor}`}>
          {formatDelta(delta, isPercentage)}
        </div>
      </div>
    </div>
  );
}
