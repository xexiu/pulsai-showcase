// @vitest-environment node
/**
 * parseApiErrorBody — user-facing messages from API error responses.
 */

import { describe, expect, it } from 'vitest';

import { parseApiErrorDetail, throwIfNotOk } from '@/utils/parseApiErrorBody';

describe('parseApiErrorDetail', () => {
  it('returns detail when it is a non-empty string', () => {
    const msg =
      'No BUY or SELL signals generated for strategy. Hybrid (model + classic) produced 721 HOLD signals.';

    expect(parseApiErrorDetail({ detail: msg }, 'Fallback')).toBe(msg);
  });

  it('returns fallback when detail is empty string', () => {
    expect(parseApiErrorDetail({ detail: '' }, 'Fallback')).toBe('Fallback');
  });

  it('returns first validation error msg when detail is array', () => {
    const body = {
      detail: [{ loc: ['body', 'symbol'], msg: 'Field required' }],
    };

    expect(parseApiErrorDetail(body, 'Fallback')).toBe('Field required');
  });

  it('returns fallback when detail is empty array', () => {
    expect(parseApiErrorDetail({ detail: [] }, 'Fallback')).toBe('Fallback');
  });

  it('returns message when detail missing but message present', () => {
    expect(parseApiErrorDetail({ message: 'Server error' }, 'Fallback')).toBe('Server error');
  });

  it('returns fallback when errorData is null or not object', () => {
    expect(parseApiErrorDetail(null, 'Fallback')).toBe('Fallback');
    expect(parseApiErrorDetail(undefined, 'Fallback')).toBe('Fallback');
    expect(parseApiErrorDetail('string', 'Fallback')).toBe('Fallback');
  });

  it('returns fallback when detail is not string or array', () => {
    expect(parseApiErrorDetail({ detail: 123 }, 'Fallback')).toBe('Fallback');
  });

  it('returns error.message from PulsAI middleware shape and strips body: prefix', () => {
    const body = {
      error: {
        code: 'VALIDATION_ERROR',
        message: 'body: Value error, model_version required for ml or hybrid',
      },
    };

    expect(parseApiErrorDetail(body, 'Fallback')).toBe(
      'Value error, model_version required for ml or hybrid'
    );
  });

  it('returns error.message for ensemble validation (feature count mismatch)', () => {
    const msg =
      'v16 has 12 features, primary (v15) has 11. All ensemble models must use the same feature set.';
    const body = {
      error: {
        code: 'VALIDATION_ERROR',
        message: msg,
      },
    };

    expect(parseApiErrorDetail(body, 'Fallback')).toBe(msg);
  });

  it('returns detail.message when detail is an object (legacy shape)', () => {
    expect(parseApiErrorDetail({ detail: { message: 'Validation failed' } }, 'Fallback')).toBe(
      'Validation failed'
    );
  });

  it('returns error.details.errors[0].msg when error.message missing', () => {
    const body = {
      error: {
        code: 'VALIDATION_ERROR',
        details: { errors: [{ msg: 'model_version required for ml or hybrid' }] },
      },
    };

    expect(parseApiErrorDetail(body, 'Fallback')).toBe('model_version required for ml or hybrid');
  });
});

describe('throwIfNotOk', () => {
  it('resolves silently when response.ok is true', async () => {
    const ok = new Response('{}', { status: 200 });

    await expect(throwIfNotOk(ok, 'Should not throw')).resolves.toBeUndefined();
  });

  it('throws Error with detail string when response is not ok', async () => {
    const r = new Response(JSON.stringify({ detail: 'Bad request payload' }), { status: 400 });

    await expect(throwIfNotOk(r, 'Failed')).rejects.toThrow('Bad request payload');
  });

  it('throws Error with PulsAI error.message and strips body: prefix', async () => {
    const r = new Response(
      JSON.stringify({
        error: { code: 'VALIDATION_ERROR', message: 'body: model_version required' },
      }),
      { status: 422 }
    );

    await expect(throwIfNotOk(r, 'Validation failed')).rejects.toThrow('model_version required');
  });

  it('throws Error with first FastAPI validation msg when detail is array', async () => {
    const r = new Response(
      JSON.stringify({ detail: [{ loc: ['body', 'symbol'], msg: 'Field required' }] }),
      { status: 422 }
    );

    await expect(throwIfNotOk(r, 'Bad input')).rejects.toThrow('Field required');
  });

  it('throws Error with "{context}: {status}" fallback when body is empty', async () => {
    const r = new Response('', { status: 500 });

    await expect(throwIfNotOk(r, 'Server error')).rejects.toThrow('Server error: 500');
  });

  it('throws Error with fallback when body is not JSON', async () => {
    const r = new Response('<html>nope</html>', { status: 502 });

    await expect(throwIfNotOk(r, 'Bad gateway')).rejects.toThrow('Bad gateway: 502');
  });

  it('throws Error with fallback for 404 with empty JSON body', async () => {
    const r = new Response('{}', { status: 404 });

    await expect(throwIfNotOk(r, 'Not found')).rejects.toThrow('Not found: 404');
  });
});
