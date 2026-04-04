import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from './http';

const getMock = vi.fn();
const postMock = vi.fn();
const patchMock = vi.fn();

vi.mock('./apiConfig', () => ({
  createApiClient: () => ({ get: getMock, post: postMock, patch: patchMock }),
}));

describe('budgetApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('maps budget summary and normalizes null arrays to []', async () => {
    const { budgetApi } = await import('./api_budget');
    getMock.mockResolvedValueOnce({
      account_balance: '10.5',
      free_pool: null,
      envelopes: null,
      loans: [{ id: '1', amount: '250', source_envelope: 111 }],
      accounts: [{ id: '2', name: null, balance: '20', currency: null }],
    });

    const result = await budgetApi.getSummary();
    expect(result.account_balance).toBe(10.5);
    expect(result.free_pool).toBe(0);
    expect(result.envelopes).toEqual([]);
    expect(result.loans[0].source_envelope).toBe('111');
    expect(result.accounts[0]).toMatchObject({ id: 2, name: '', balance: 20, currency: 'PLN' });
  });

  it('omits optional query params when null/undefined for getTransactions', async () => {
    const { budgetApi } = await import('./api_budget');
    getMock.mockResolvedValueOnce({});

    await budgetApi.getTransactions(10, null, undefined);

    expect(getMock).toHaveBeenCalledWith('/transactions', {
      params: { account_id: 10, envelope_id: undefined, category_id: undefined },
    });
  });

  it.each([400, 401, 403, 404, 409, 422, 500])('keeps HttpError shape for status %s', async (status) => {
    const { budgetApi } = await import('./api_budget');
    const apiError = new HttpError('Validation failed', status, {
      error: { code: 'E_VALIDATION', message: 'Validation failed', details: { field: 'amount' } },
    });
    postMock.mockRejectedValueOnce(apiError);

    await expect(budgetApi.addIncome(1, 200)).rejects.toMatchObject({
      status,
      message: 'Validation failed',
      data: {
        error: {
          code: 'E_VALIDATION',
          message: 'Validation failed',
          details: { field: 'amount' },
        },
      },
    });
  });
});
