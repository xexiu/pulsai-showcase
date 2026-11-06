/**
 * queryFetchersBilling.ts — unit tests for billing fetchers.
 *
 * BEHAVIOR: URLs, methods, auth flags, JSON bodies, CSV download flow, error messages.
 * Pattern mirrors queryFetchersTrading.test.ts.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  BillingCheckoutConflictError,
  createBillingPortalSession,
  createCheckoutSession,
  downloadBillingInvoicesCsv,
  fetchBillingInvoices,
  trackPricingCardClick,
} from '@/config/queryFetchersBilling';
import type { AppFetchOptions } from '@/services/api';

const mockAppFetch = vi.fn();

vi.mock('@/services/api', () => ({
  appFetch: (opts: unknown) => mockAppFetch(opts),
}));

function mockOk<T>(
  data: T,
  headerMap?: Record<string, string>
): { ok: boolean; status: number; headers: Headers; json: () => Promise<T> } {
  const headers = new Headers(headerMap ?? undefined);

  return { ok: true, status: 200, headers, json: () => Promise.resolve(data) };
}

function mockJsonError(
  status: number,
  body: Record<string, unknown>
): {
  ok: boolean;
  status: number;
  headers: Headers;
  json: () => Promise<Record<string, unknown>>;
} {
  return {
    ok: false,
    status,
    headers: new Headers(),
    json: () => Promise.resolve(body),
  };
}

function mockCsvOk(blobText = 'id,status\n'): {
  ok: boolean;
  status: number;
  headers: Headers;
  blob: () => Promise<Blob>;
} {
  return {
    ok: true,
    status: 200,
    headers: new Headers(),
    blob: () => Promise.resolve(new Blob([blobText], { type: 'text/csv' })),
  };
}

describe('queryFetchersBilling', () => {
  beforeEach(() => {
    mockAppFetch.mockReset();
    sessionStorage.clear();
  });

  describe('trackPricingCardClick', () => {
    it('POSTs pricing-card-click with auth when authenticated and JSON body including checkout_tier', async () => {
      mockAppFetch.mockResolvedValueOnce({ ok: true, status: 204 });

      const controller = new AbortController();

      await trackPricingCardClick(
        {
          tier: 'starter',
          ctaLabel: 'Upgrade',
          ctaHref: '/pricing',
          checkoutTier: 'pro',
          authenticated: true,
        },
        controller.signal
      );

      const call = mockAppFetch.mock.calls[0]?.[0] as Record<string, unknown>;

      expect(call['url'] as string).toContain('/api/v1/billing/pricing-card-click');
      expect(call['method']).toBe('POST');
      expect(call['auth']).toBe(true);
      expect(call['signal']).toBe(controller.signal);
      expect(JSON.parse(String(call['body']))).toEqual({
        tier: 'starter',
        cta_label: 'Upgrade',
        cta_href: '/pricing',
        checkout_tier: 'pro',
      });
    });

    it('POSTs without auth when unauthenticated and omits checkout_tier from JSON when not provided', async () => {
      mockAppFetch.mockResolvedValueOnce({ ok: true, status: 204 });

      await trackPricingCardClick({
        tier: 'free',
        ctaLabel: 'See plans',
        ctaHref: '/en/pricing',
        authenticated: false,
      });

      const call = mockAppFetch.mock.calls[0]?.[0] as Record<string, unknown>;

      expect(call['auth']).toBe(false);
      const body = JSON.parse(String(call['body'])) as Record<string, unknown>;

      expect(body['checkout_tier']).toBeUndefined();
      expect(body['tier']).toBe('free');
    });

    it('propagates when appFetch rejects', async () => {
      mockAppFetch.mockRejectedValueOnce(new Error('network down'));

      await expect(
        trackPricingCardClick({
          tier: 'elite',
          ctaLabel: 'Go',
          ctaHref: '/x',
          authenticated: true,
        })
      ).rejects.toThrow('network down');
    });
  });

  describe('fetchBillingInvoices', () => {
    it('GETs invoices with auth and returns invoices array from JSON', async () => {
      const invoices = [
        {
          id: 'in_1',
          status: 'paid',
          amount_paid: 1000,
          currency: 'eur',
          created: 1_700_000_000,
          hosted_invoice_url: 'https://stripe.example/inv',
          invoice_pdf: 'https://stripe.example/pdf',
        },
      ];

      mockAppFetch.mockResolvedValueOnce(mockOk({ invoices }));

      const out = await fetchBillingInvoices();
      const call = mockAppFetch.mock.calls[0]?.[0] as AppFetchOptions;

      expect(call.url).toContain('/api/v1/billing/invoices');
      expect(call.method).toBeUndefined();
      expect(call.auth).toBe(true);
      expect(out).toEqual(invoices);
    });

    it('forwards AbortSignal when provided', async () => {
      mockAppFetch.mockResolvedValueOnce(mockOk({ invoices: [] }));
      const ac = new AbortController();

      await fetchBillingInvoices(ac.signal);

      const call = mockAppFetch.mock.calls[0]?.[0] as { signal?: AbortSignal };

      expect(call.signal).toBe(ac.signal);
    });

    it('throws fixed message when response is not ok', async () => {
      mockAppFetch.mockResolvedValueOnce(mockJsonError(500, { detail: 'ignored' }));

      await expect(fetchBillingInvoices()).rejects.toThrow('Failed to load invoices');
    });
  });

  describe('downloadBillingInvoicesCsv', () => {
    it('GETs export.csv with auth, builds blob URL, clicks anchor, revokes URL on success', async () => {
      const createSpy = vi
        .spyOn(window.URL, 'createObjectURL')
        .mockReturnValue('blob:test-invoices');
      const revokeSpy = vi.spyOn(window.URL, 'revokeObjectURL');
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

      mockAppFetch.mockResolvedValueOnce(mockCsvOk('a,b\n1,2\n'));

      await downloadBillingInvoicesCsv();

      const call = mockAppFetch.mock.calls[0]?.[0] as { url: string; auth?: boolean };

      expect(call.url).toContain('/api/v1/billing/invoices/export.csv');
      expect(call.auth).toBe(true);
      expect(createSpy).toHaveBeenCalled();
      expect(revokeSpy).toHaveBeenCalledWith('blob:test-invoices');
      expect(clickSpy).toHaveBeenCalled();

      createSpy.mockRestore();
      revokeSpy.mockRestore();
      clickSpy.mockRestore();
    });

    it('throws with parseApiErrorDetail message from JSON body on non-ok', async () => {
      mockAppFetch.mockResolvedValueOnce(mockJsonError(403, { detail: 'billing disabled' }));

      await expect(downloadBillingInvoicesCsv()).rejects.toThrow('billing disabled');
    });

    it('throws fallback when non-ok body has no usable message', async () => {
      mockAppFetch.mockResolvedValueOnce(mockJsonError(500, {}));

      await expect(downloadBillingInvoicesCsv()).rejects.toThrow('Failed to export invoice CSV.');
    });

    it('tolerates non-JSON error body and uses fallback message', async () => {
      mockAppFetch.mockResolvedValueOnce({
        ok: false,
        status: 502,
        headers: new Headers(),
        json: () => Promise.reject(new Error('not json')),
      });

      await expect(downloadBillingInvoicesCsv()).rejects.toThrow('Failed to export invoice CSV.');
    });
  });

  describe('createCheckoutSession', () => {
    it('POSTs checkout-session with auth, default currency eur, and returns session URL', async () => {
      mockAppFetch.mockResolvedValueOnce(mockOk({ url: 'https://checkout.stripe.com/csess_test' }));

      const out = await createCheckoutSession({ tier: 'starter' });
      const call = mockAppFetch.mock.calls[0]?.[0] as Record<string, unknown>;

      expect(call['method']).toBe('POST');
      expect(call['auth']).toBe(true);
      expect(call['url'] as string).toContain('/api/v1/billing/checkout-session');
      expect(JSON.parse(String(call['body']))).toEqual({ tier: 'starter', currency: 'eur' });
      expect((call['headers'] as Record<string, string>)['Idempotency-Key']).toBeTruthy();
      expect(out.url).toContain('checkout.stripe.com');
    });

    it('reuses the same Idempotency-Key for repeated checkout calls with the same tier and currency', async () => {
      mockAppFetch.mockResolvedValue(mockOk({ url: 'https://checkout.stripe.com/retry' }));

      await createCheckoutSession({ tier: 'pro', currency: 'eur' });
      await createCheckoutSession({ tier: 'pro', currency: 'eur' });

      const first = mockAppFetch.mock.calls[0]?.[0] as Record<string, unknown>;
      const second = mockAppFetch.mock.calls[1]?.[0] as Record<string, unknown>;

      expect((first['headers'] as Record<string, string>)['Idempotency-Key']).toBe(
        (second['headers'] as Record<string, string>)['Idempotency-Key']
      );
    });

    it('includes explicit currency in JSON body when provided', async () => {
      mockAppFetch.mockResolvedValueOnce(mockOk({ url: 'https://checkout.stripe.com/usd' }));

      await createCheckoutSession({ tier: 'pro', currency: 'usd' });

      const call = mockAppFetch.mock.calls[0]?.[0] as { body?: string; signal?: AbortSignal };
      const parsed = JSON.parse(String(call.body)) as { tier: string; currency: string };

      expect(parsed.currency).toBe('usd');
      expect(parsed.tier).toBe('pro');
    });

    it('forwards AbortSignal when provided', async () => {
      mockAppFetch.mockResolvedValueOnce(mockOk({ url: 'https://x' }));
      const ac = new AbortController();

      await createCheckoutSession({ tier: 'elite' }, { signal: ac.signal });

      const call = mockAppFetch.mock.calls[0]?.[0] as { signal?: AbortSignal };

      expect(call.signal).toBe(ac.signal);
    });

    it('throws with parseApiErrorDetail message on non-ok', async () => {
      mockAppFetch.mockResolvedValueOnce(
        mockJsonError(400, { error: { message: 'body: tier not available for account' } })
      );

      await expect(createCheckoutSession({ tier: 'starter' })).rejects.toThrow(
        'tier not available for account'
      );
    });

    it('throws BillingCheckoutConflictError on 409 with use_billing_portal', async () => {
      mockAppFetch.mockResolvedValueOnce(
        mockJsonError(409, {
          error: {
            message:
              'You already have a paid subscription. Use the billing portal to change your plan.',
            details: { use_billing_portal: true },
          },
        })
      );

      await expect(createCheckoutSession({ tier: 'pro' })).rejects.toBeInstanceOf(
        BillingCheckoutConflictError
      );
    });

    it('throws checkout fallback when error body is empty', async () => {
      mockAppFetch.mockResolvedValueOnce(mockJsonError(503, {}));

      await expect(createCheckoutSession({ tier: 'pro' })).rejects.toThrow(
        'Checkout is not available. Please try again later.'
      );
    });

    it('tolerates non-JSON error body on non-ok and uses checkout fallback', async () => {
      mockAppFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        headers: new Headers(),
        json: () => Promise.reject(new Error('not json')),
      });

      await expect(createCheckoutSession({ tier: 'starter' })).rejects.toThrow(
        'Checkout is not available. Please try again later.'
      );
    });
  });

  describe('createBillingPortalSession', () => {
    it('POSTs portal-session with auth and returns portal URL', async () => {
      mockAppFetch.mockResolvedValueOnce(
        mockOk({ url: 'https://billing.stripe.com/session/test' })
      );

      const out = await createBillingPortalSession();
      const call = mockAppFetch.mock.calls[0]?.[0] as Record<string, unknown>;

      expect(call['method']).toBe('POST');
      expect(call['auth']).toBe(true);
      expect(call['url'] as string).toContain('/api/v1/billing/portal-session');
      expect(call['body']).toBeUndefined();
      expect((call['headers'] as Record<string, string>)['Idempotency-Key']).toBeTruthy();
      expect(out.url).toContain('billing.stripe.com');
    });

    it('reuses the same Idempotency-Key on repeated portal opens', async () => {
      mockAppFetch.mockResolvedValue(mockOk({ url: 'https://billing.stripe.com/session/test' }));

      await createBillingPortalSession();
      await createBillingPortalSession();

      const first = mockAppFetch.mock.calls[0]?.[0] as Record<string, unknown>;
      const second = mockAppFetch.mock.calls[1]?.[0] as Record<string, unknown>;

      expect((first['headers'] as Record<string, string>)['Idempotency-Key']).toBe(
        (second['headers'] as Record<string, string>)['Idempotency-Key']
      );
    });

    it('forwards AbortSignal when provided', async () => {
      mockAppFetch.mockResolvedValueOnce(mockOk({ url: 'https://billing.example/p' }));
      const ac = new AbortController();

      await createBillingPortalSession({ signal: ac.signal });

      const call = mockAppFetch.mock.calls[0]?.[0] as { signal?: AbortSignal };

      expect(call.signal).toBe(ac.signal);
    });

    it('throws with parseApiErrorDetail message on non-ok', async () => {
      mockAppFetch.mockResolvedValueOnce(mockJsonError(401, { detail: 'not subscribed' }));

      await expect(createBillingPortalSession()).rejects.toThrow('not subscribed');
    });

    it('throws portal fallback when error body has no message', async () => {
      mockAppFetch.mockResolvedValueOnce(mockJsonError(500, {}));

      await expect(createBillingPortalSession()).rejects.toThrow(
        'Billing portal is not available. Please try again later.'
      );
    });

    it('tolerates non-JSON error body on non-ok and uses portal fallback', async () => {
      mockAppFetch.mockResolvedValueOnce({
        ok: false,
        status: 502,
        headers: new Headers(),
        json: () => Promise.reject(new Error('not json')),
      });

      await expect(createBillingPortalSession()).rejects.toThrow(
        'Billing portal is not available. Please try again later.'
      );
    });
  });
});
