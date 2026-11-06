import { BillingCheckoutConflictError } from '@/types/billing-api';
import { HTTP_STATUS } from '@/utils/constants/extended';
import { parseApiErrorDetail } from '@/utils/parseApiErrorBody';

type ApiErrorBody = {
  error?: {
    details?: {
      use_billing_portal?: boolean;
    };
  };
};

/**
 * Map checkout-session failures; 409 + use_billing_portal → redirectable conflict.
 */
export function parseBillingCheckoutFailure(
  status: number,
  errorData: unknown,
  fallback: string
): Error {
  const message = parseApiErrorDetail(errorData, fallback);

  if (status === HTTP_STATUS.CONFLICT) {
    const body = errorData as ApiErrorBody;

    if (body.error?.details?.use_billing_portal === true) {
      return new BillingCheckoutConflictError(message);
    }
  }

  return new Error(message);
}
