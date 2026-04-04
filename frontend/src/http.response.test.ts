import { describe, expect, it } from 'vitest';
import {
  extractErrorMessage,
  extractErrorMessageFromUnknown,
  extractPayload,
  parseJsonApiResponse,
} from './http/response';

describe('http/response', () => {
  it('extractPayload returns payload and throws for invalid envelope', () => {
    expect(extractPayload<{ id: number }>({ payload: { id: 7 } })).toEqual({ id: 7 });
    expect(() => extractPayload({ invalid: true })).toThrow('Nie udało się przetworzyć odpowiedzi serwera.');
  });

  it('extractErrorMessage prefers message, then details and code', () => {
    expect(extractErrorMessage({ error: { code: 'E1', message: 'Bad request' } })).toBe('Bad request');
    expect(extractErrorMessage({ error: { code: 'E2', message: '', details: { amount: ['must be positive'] } } })).toBe(
      'amount: must be positive'
    );
    expect(extractErrorMessage({ error: { code: 'FALLBACK_CODE', message: ' ' } })).toBe('FALLBACK_CODE');
  });

  it('extractErrorMessageFromUnknown handles body and plain errors', () => {
    expect(
      extractErrorMessageFromUnknown({
        body: { error: { code: 'E', message: 'From body', details: { field: 'invalid' } } },
      })
    ).toBe('From body');

    expect(extractErrorMessageFromUnknown(new Error('Network down'))).toBe('Network down');
  });

  it('parseJsonApiResponse unwraps payload on success', async () => {
    const response = new Response(JSON.stringify({ payload: { ids: [1, 2, 3] } }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });

    await expect(parseJsonApiResponse<{ ids: number[] }>(response)).resolves.toEqual({ ids: [1, 2, 3] });
  });

  it('parseJsonApiResponse sets error.body for non-2xx API errors', async () => {
    const response = new Response(
      JSON.stringify({ error: { code: 'VALIDATION_ERROR', message: 'Invalid payload', details: { field: 'name' } } }),
      { status: 422 }
    );

    await expect(parseJsonApiResponse(response)).rejects.toMatchObject({
      message: 'Invalid payload',
      body: {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Invalid payload',
          details: { field: 'name' },
        },
      },
    });
  });
});
