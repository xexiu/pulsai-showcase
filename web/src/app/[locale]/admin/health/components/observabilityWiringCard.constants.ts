import { API_BASE_URL } from '@/config/api';

/** Mount path for the Prometheus scrape endpoint (mirrors backend constant). */
const PROMETHEUS_METRICS_ROUTE = '/metrics';

/**
 * Full URL to open raw Prometheus exposition in the browser (API origin + route).
 * WHY: Relative `/metrics` would hit the Next.js origin, not FastAPI.
 */
export function getPrometheusMetricsDocumentUrl(): string {
  const base = API_BASE_URL.replace(/\/$/, '');

  return `${base}${PROMETHEUS_METRICS_ROUTE}`;
}
