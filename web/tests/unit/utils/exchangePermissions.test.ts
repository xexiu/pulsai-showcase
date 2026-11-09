// @vitest-environment node
/**
 * exchangePermissions — getGrantedPermissions + isReadOnly.
 */

import { describe, expect, it } from 'vitest';

import { getGrantedPermissions, isReadOnly } from '@/utils/exchangePermissions';

describe('getGrantedPermissions', () => {
  it('returns only keys that are true', () => {
    expect(getGrantedPermissions({ read: true, trade: false, withdraw: true })).toEqual([
      'read',
      'withdraw',
    ]);
  });

  it('returns empty array when no permissions are true', () => {
    expect(getGrantedPermissions({})).toEqual([]);
  });

  it('ignores unknown keys', () => {
    expect(getGrantedPermissions({ read: true, custom: true })).toEqual(['read']);
  });
});

describe('isReadOnly', () => {
  it('returns true when read=true but trade is absent', () => {
    expect(isReadOnly({ read: true })).toBe(true);
  });

  it('returns false when trade=true', () => {
    expect(isReadOnly({ read: true, trade: true })).toBe(false);
  });

  it('returns false when no permissions are granted', () => {
    expect(isReadOnly({})).toBe(false);
  });
});
