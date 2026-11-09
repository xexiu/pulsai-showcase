import { describe, expect, it } from 'vitest';

import {
  loginErrorBannerClassName,
  resolveLoginErrorDisplay,
} from '@/app/[locale]/(auth)/login/loginErrorDisplay';

describe('resolveLoginErrorDisplay', () => {
  it('prefers serverError over authError to avoid duplicate banners', () => {
    expect(
      resolveLoginErrorDisplay('Access restricted', 'sessionExpired', (k) => `t:${k}`)
    ).toEqual({ message: 'Access restricted', variant: 'server' });
  });

  it('translates auth error keys when only authError is set', () => {
    expect(resolveLoginErrorDisplay(null, 'sessionExpired', (k) => `t:${k}`)).toEqual({
      message: 't:sessionExpired',
      variant: 'auth',
    });
  });

  it('passes through free-form authError messages', () => {
    expect(resolveLoginErrorDisplay(null, 'raw boom', (k) => `t:${k}`)).toEqual({
      message: 'raw boom',
      variant: 'auth',
    });
  });

  it('returns null when neither error is set', () => {
    expect(resolveLoginErrorDisplay(null, null, (k) => k)).toBeNull();
  });
});

describe('loginErrorBannerClassName', () => {
  it('uses destructive styles for server variant', () => {
    expect(loginErrorBannerClassName('server')).toContain('destructive');
  });

  it('uses amber styles for auth variant', () => {
    expect(loginErrorBannerClassName('auth')).toContain('amber');
  });
});
