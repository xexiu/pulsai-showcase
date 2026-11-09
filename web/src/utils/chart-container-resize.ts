/**
 * Resolve lightweight-charts dimensions from the mount container (resize + initial mount).
 */

import { FULL_CHART_MIN_HEIGHT_PX } from '@/utils/constants';

export type ChartContainerResizeInput = {
  clientWidth: number;
  clientHeight: number;
  fallbackHeight: number;
  fitHeightToContainer: boolean;
};

export type ChartContainerResizeDimensions = {
  width: number;
  height: number;
};

function clampChartHeight(px: number): number {
  return Math.max(FULL_CHART_MIN_HEIGHT_PX, Math.floor(px));
}

/**
 * Dimensions for createChart / applyOptions on container resize.
 */
export function resolveChartContainerResizeDimensions(
  input: ChartContainerResizeInput
): ChartContainerResizeDimensions {
  const width = Math.max(0, Math.floor(input.clientWidth));

  if (!input.fitHeightToContainer) {
    return { width, height: clampChartHeight(input.fallbackHeight) };
  }

  const measured = input.clientHeight > 0 ? input.clientHeight : input.fallbackHeight;

  return { width, height: clampChartHeight(measured) };
}
