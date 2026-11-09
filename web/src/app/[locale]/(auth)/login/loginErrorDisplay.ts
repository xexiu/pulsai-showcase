/**
 * Prefer one login error banner: performLogin setError() AND rethrows into
 * useAsyncAction, which previously rendered amber + red duplicates.
 */

import { isAuthErrorKey } from '@/services/api';

export type LoginErrorDisplay = {
  message: string;
  variant: 'server' | 'auth';
};

export function resolveLoginErrorDisplay(
  serverError: string | null,
  authError: string | null,
  translateAuthKey: (key: string) => string
): LoginErrorDisplay | null {
  if (serverError) {
    return { message: serverError, variant: 'server' };
  }

  if (!authError) {
    return null;
  }

  if (isAuthErrorKey(authError)) {
    return { message: translateAuthKey(authError), variant: 'auth' };
  }

  return { message: authError, variant: 'auth' };
}

export function loginErrorBannerClassName(variant: LoginErrorDisplay['variant']): string {
  if (variant === 'server') {
    return 'mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive';
  }

  return 'mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200';
}
