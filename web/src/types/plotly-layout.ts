/**
 * Plotly.js layout/config/trace shapes used by react-plotly.js.
 *
 * WHY permissive `unknown` instead of `any`:
 * - Plotly objects are deeply nested and vary by chart mode
 * - We only need structural typing for our chart helpers (TS + ESLint clean)
 * - @types/plotly.js Layout is available but often stricter than our partial builds
 */

/** Layout object passed to Plotly.react (partial domain-specific layout). */
export type PlotlyLayout = Record<string, unknown>;

/** Plotly `config` (toolbar, export, responsive). */
export type PlotlyConfig = Record<string, unknown>;

/** Single trace: type discriminator + arbitrary series fields (x, y, line, …). */
export type PlotlyTraceData = {
  type: string;
} & Record<string, unknown>;
