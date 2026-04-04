import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();
const postMock = vi.fn();
const putMock = vi.fn();
const deleteMock = vi.fn();

vi.mock('./apiConfig', () => ({
  createApiClient: () => ({ get: getMock, post: postMock, put: putMock, delete: deleteMock }),
}));

describe('symbolMapApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('normalizes list/create/update payloads', async () => {
    const { symbolMapApi } = await import('./api_symbol_map');
    getMock.mockResolvedValueOnce([{ id: '3', symbol_input: 'kghm', ticker: null, currency: 'CAD', created_at: 77 }]);

    await expect(symbolMapApi.getAll()).resolves.toEqual([
      { id: 3, symbol_input: 'kghm', ticker: '', currency: null, created_at: null },
    ]);

    postMock.mockResolvedValueOnce({ id: 1, symbol_input: 'a', ticker: 'AAPL', currency: 'USD', created_at: '2026-01-01' });
    await symbolMapApi.create({ symbol_input: 'a', ticker: 'AAPL', currency: 'USD' });
    expect(postMock).toHaveBeenCalledWith('', { symbol_input: 'a', ticker: 'AAPL', currency: 'USD' });

    putMock.mockResolvedValueOnce({ id: 1, symbol_input: 'a', ticker: 'MSFT', currency: 'EUR', created_at: null });
    await symbolMapApi.update(1, { ticker: 'MSFT' });
    expect(putMock).toHaveBeenCalledWith('/1', { ticker: 'MSFT' });
  });
});
