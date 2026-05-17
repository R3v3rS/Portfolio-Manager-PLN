import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();

vi.mock('./apiConfig', () => ({
  ANALYTICS_ENDPOINTS: { summary: '/summary' },
  createApiClient: () => ({ get: getMock }),
}));

describe('analyticsApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses the unwrapped HTTP payload and normalizes legacy analytics fields', async () => {
    const { analyticsApi } = await import('./api_analytics');
    getMock.mockResolvedValueOnce({
      performance_summary: {
        sharpe_ratio: 1.23,
        max_drawdown: { value: -0.15 },
      },
      portfolio_var: {
        var_1d_pct: -0.012,
      },
      correlation_risk: {
        recharts_data: [{ symbol: 'AAA', AAA: 1, BBB: 0.4 }],
      },
      diversification: {
        score: 72,
        by_sector: [{ sector: 'Technology', weight: 0.6 }],
      },
    });

    const result = await analyticsApi.getSummary(7, 3);

    expect(getMock).toHaveBeenCalledWith('/summary', {
      params: { portfolio_id: 7, sub_portfolio_id: 3 },
    });
    expect(result.performance?.sharpe_ratio).toBe(1.23);
    expect(result.risk?.var_1d_percent).toBe(-0.012);
    expect(result.correlation?.recharts_data).toEqual([{ symbol: 'AAA', AAA: 1, BBB: 0.4 }]);
    expect(result.diversification?.score).toBe(72);
  });
});
