/**
 * Convert snake_case key to display label (e.g. sweep_bullish → "sweep bullish").
 */
export function humanizeSnakeCase(key: string): string {
  return key.replace(/_/g, ' ');
}

/**
 * Convert snake_case to Title Case.
 */
export function formatSnakeCase(snakeCase: string): string {
  return snakeCase
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
