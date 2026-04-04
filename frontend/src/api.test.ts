import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from './http';

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock('./apiConfig', () => ({
  createApiClient: () => ({ get: getMock, post: postMock, put: vi.fn(), delete: vi.fn(), patch: vi.fn() }),
}));

describe('portfolioApi + helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('normalizes list response with safe defaults', async () => {
    const { portfolioApi } = await import('./api');
    getMock.mockResolvedValueOnce({
      portfolios: [{ id: '12', account_type: 'UNKNOWN', name: null, current_cash: '9.5', children: null }],
    });

    const result = await portfolioApi.list();
    expect(result.portfolios[0]).toMatchObject({
      id: 12,
      name: '',
      account_type: 'STANDARD',
      current_cash: 9.5,
    });
  });

  it('maps getPriceHistory with null->[] and nullable last_updated', async () => {
    const { portfolioApi } = await import('./api');
    getMock.mockResolvedValueOnce({ history: null, last_updated: 123 });

    await expect(portfolioApi.getPriceHistory('AAPL')).resolves.toEqual({ history: [], last_updated: null });
  });

  it('serializes optional benchmark query only when provided', async () => {
    const { portfolioApi } = await import('./api');
    getMock.mockResolvedValueOnce({ history: [] });
    await portfolioApi.getMonthlyHistory(7);
    expect(getMock).toHaveBeenCalledWith('/history/monthly/7', { params: undefined });

    getMock.mockResolvedValueOnce({ history: [] });
    await portfolioApi.getMonthlyHistory(7, 'SP500');
    expect(getMock).toHaveBeenCalledWith('/history/monthly/7', { params: { benchmark: 'SP500' } });
  });

  it.each([400, 401, 403, 404, 409, 422, 500])('normalizeXtbImportError keeps error envelope shape for status %s', async (status) => {
    const { normalizeXtbImportError } = await import('./api');
    const error = new HttpError('Import failed', status, {
      error: {
        code: 'XTB_IMPORT_FAILED',
        message: 'Import failed',
        details: { missing_symbols: ['AAA', 'BBB'] },
      },
    });

    const normalized = normalizeXtbImportError(error);
    expect(normalized).toEqual({
      ok: false,
      message: 'Import failed',
      missingSymbols: ['AAA', 'BBB'],
      potentialConflicts: [],
    });
  });

  it('sends importXtbCsv form data with optional fields only when provided', async () => {
    const { portfolioApi } = await import('./api');
    postMock.mockResolvedValueOnce({ message: 'ok', missing_symbols: [] });
    const file = new File(['date,ticker'], 'xtb.csv', { type: 'text/csv' });

    await portfolioApi.importXtbCsv(4, file, ['hash-a'], null);

    const [, body] = postMock.mock.calls[0];
    expect(postMock.mock.calls[0][0]).toBe('/4/import/xtb');
    expect(body).toBeInstanceOf(FormData);
    const form = body as FormData;
    expect(form.get('file')).toBe(file);
    expect(form.get('confirmed_hashes')).toBe('["hash-a"]');
    expect(form.get('sub_portfolio_id')).toBeNull();
  });
});
