/**
 * Stripe Checkout / invoices — API-facing types (SoT).
 * Fetchers import from here; no shared types in queryFetchers*.ts bodies.
 *
 * @see config/queryFetchersBilling.ts
 */

export type CheckoutTier = 'starter' | 'pro' | 'elite';

export type BillingCurrency = 'eur' | 'usd';

export type CheckoutSessionResponse = {
  url: string;
};

export type BillingInvoiceRow = {
  id: string;
  status: string | null;
  amount_paid: number | null;
  currency: string | null;
  created: number | null;
  hosted_invoice_url: string | null;
  invoice_pdf: string | null;
};

export type BillingInvoicesResponse = {
  invoices: BillingInvoiceRow[];
};

export type BillingPortalSessionResponse = {
  url: string;
};

/** Thrown when checkout-session returns 409 with use_billing_portal (paid user). */
export class BillingCheckoutConflictError extends Error {
  readonly useBillingPortal = true;

  constructor(message: string) {
    super(message);
    this.name = 'BillingCheckoutConflictError';
  }
}
