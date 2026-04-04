import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();
const postMock = vi.fn();
const deleteMock = vi.fn();

vi.mock('./apiConfig', () => ({
  createApiClient: () => ({ get: getMock, post: postMock, delete: deleteMock }),
}));

describe('radarApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('maps getAll with null-safe conversions and filters empty tickers', async () => {
    const { radarApi } = await import('./api_radar');
    getMock.mockResolvedValueOnce([
      { ticker: 'AAPL', price: '201.2', quantity: null, is_watched: true },
      { ticker: '', price: 1 },
    ]);

    const result = await radarApi.getAll(true);

    expect(getMock).toHaveBeenCalledWith('/', { params: { refresh: 1 } });
    expect(result).toEqual([
      expect.objectContaining({ ticker: 'AAPL', price: 201.2, quantity: 0, is_watched: true }),
    ]);
  });

  it('maps action response with fallback message and ticker normalization', async () => {
    const { radarApi } = await import('./api_radar');
    postMock.mockResolvedValueOnce({ message: ' ', tickers: ['MSFT', 123] });

    const result = await radarApi.refresh();
    expect(postMock).toHaveBeenCalledWith('/refresh', { tickers: [] });
    expect(result).toEqual({ message: 'Odświeżono radar.', tickers: ['MSFT', '123'] });
  });

  it('maps analysis object safely when nested blocks are missing', async () => {
    const { radarApi } = await import('./api_radar');
    getMock.mockResolvedValueOnce({
      score: '7',
      fundamentals: { trailingPE: '12.4' },
      analyst: { recommendationKey: ' buy ' },
    });

    const result = await radarApi.getAnalysis('AAPL');
    expect(result.score).toBe(7);
    expect(result.fundamentals.trailingPE).toBe(12.4);
    expect(result.market.averageVolume).toBeNull();
    expect(result.analyst.recommendationKey).toBe('buy');
  });
});
