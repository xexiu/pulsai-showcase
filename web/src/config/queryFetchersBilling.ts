/**
 * Stripe Checkout and Customer Portal — authenticated session creation.
 *
 * @see apps/api/src/api/v1/endpoints/billing.py
 */

import { appFetch } from '@/services/api';
import type {
  BillingCurrency,
  BillingInvoiceRow,
  BillingInvoicesResponse,
  BillingPortalSessionResponse,
  CheckoutSessionResponse,
  CheckoutTier,
} from '@/types/billing-api';
import { resolveBillingCheckoutIdempotencyKey } from '@/utils/billing/checkoutIdempotencyKey';
import { parseBillingCheckoutFailure } from '@/utils/billing/parseBillingCheckoutFailure';
import { resolveBillingPortalIdempotencyKey } from '@/utils/billing/portalIdempotencyKey';
import {
  adminMutationRequestHeaders,
  type AdminHttpMutationOptions,
} from '@/utils/http-idempotency';
import { parseApiErrorDetail } from '@/utils/parseApiErrorBody';

export type {
  BillingCurrency,
  BillingInvoiceRow,
  BillingPortalSessionResponse,
  CheckoutSessionResponse,
  CheckoutTier,
} from '@/types/billing-api';

export { BillingCheckoutConflictError } from '@/types/billing-api';

type PricingTier = 'free' | CheckoutTier;

export async function trackPricingCardClick(
  options: {
    tier: PricingTier;
    ctaLabel: string;
    ctaHref: string;
    checkoutTier?: CheckoutTier;
    authenticated: boolean;
  },
  signal?: AbortSignal
): Promise<void> {
  await appFetch({
    signal,
    url: '/api/v1/billing/pricing-card-click',
    method: 'POST',
    auth: options.authenticated,
    body: JSON.stringify({
      tier: options.tier,
      cta_label: options.ctaLabel,
      cta_href: options.ctaHref,
      checkout_tier: options.checkoutTier,
    }),
  });
}

export async function fetchBillingInvoices(signal?: AbortSignal): Promise<BillingInvoiceRow[]> {
  const response = await appFetch({
    signal,
    url: '/api/v1/billing/invoices',
    auth: true,
  });

  if (!response.ok) {
    throw new Error('Failed to load invoices');
  }

  const json = (await response.json()) as BillingInvoicesResponse;

  return json.invoices;
}

export async function downloadBillingInvoicesCsv(signal?: AbortSignal): Promise<void> {
  const response = await appFetch({
    signal,
    url: '/api/v1/billing/invoices/export.csv',
    auth: true,
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as unknown;

    throw new Error(parseApiErrorDetail(errorData, 'Failed to export invoice CSV.'));
  }

  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const link = window.document.createElement('a');

  link.href = downloadUrl;
  link.download = 'pulsai-billing-invoices.csv';
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(downloadUrl);
}

export async function createCheckoutSession(
  options: {
    tier: CheckoutTier;
    currency?: BillingCurrency;
  },
  mutationOptions?: AdminHttpMutationOptions
): Promise<CheckoutSessionResponse> {
  const currency = options.currency ?? 'eur';
  const idempotencyKey =
    mutationOptions?.idempotencyKey ?? resolveBillingCheckoutIdempotencyKey(options.tier, currency);
  const headers = adminMutationRequestHeaders({
    ...mutationOptions,
    idempotencyKey,
  });
  const response = await appFetch({
    signal: mutationOptions?.signal,
    url: '/api/v1/billing/checkout-session',
    method: 'POST',
    auth: true,
    body: JSON.stringify({
      tier: options.tier,
      currency,
    }),
    ...(headers ? { headers } : {}),
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as unknown;

    throw parseBillingCheckoutFailure(
      response.status,
      errorData,
      'Checkout is not available. Please try again later.'
    );
  }

  return response.json() as Promise<CheckoutSessionResponse>;
}

export async function createBillingPortalSession(
  mutationOptions?: AdminHttpMutationOptions
): Promise<BillingPortalSessionResponse> {
  const idempotencyKey = mutationOptions?.idempotencyKey ?? resolveBillingPortalIdempotencyKey();
  const headers = adminMutationRequestHeaders({
    ...mutationOptions,
    idempotencyKey,
  });
  const response = await appFetch({
    signal: mutationOptions?.signal,
    url: '/api/v1/billing/portal-session',
    method: 'POST',
    auth: true,
    ...(headers ? { headers } : {}),
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as unknown;

    throw new Error(
      parseApiErrorDetail(errorData, 'Billing portal is not available. Please try again later.')
    );
  }

  return response.json() as Promise<BillingPortalSessionResponse>;
}
