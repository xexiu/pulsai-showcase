/**
 * Prometheus metrics document URL (API origin + /metrics).
 * @see observabilityWiringCard.constants.ts
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

describe('getPrometheusMetricsDocumentUrl', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('strips a trailing slash from NEXT_PUBLIC_API_URL before appending /metrics', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://localhost:8000/');
    const { getPrometheusMetricsDocumentUrl } =
      await import('@/app/[locale]/admin/health/components/observabilityWiringCard.constants');

    expect(getPrometheusMetricsDocumentUrl()).toBe('http://localhost:8000/metrics');
  });

  it('uses custom API origin when set before module load', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://192.168.1.10:9000');
    const { getPrometheusMetricsDocumentUrl } =
      await import('@/app/[locale]/admin/health/components/observabilityWiringCard.constants');

    expect(getPrometheusMetricsDocumentUrl()).toBe('http://192.168.1.10:9000/metrics');
  });
});
