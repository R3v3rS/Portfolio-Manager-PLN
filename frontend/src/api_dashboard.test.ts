import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();

vi.mock('./apiConfig', () => ({
  createApiClient: () => ({ get: getMock }),
}));

describe('dashboardApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('maps numeric/string fields and falls back to zero/null defaults', async () => {
    const { dashboardApi, EMPTY_GLOBAL_SUMMARY } = await import('./api_dashboard');

    getMock.mockResolvedValueOnce({
      net_worth: '1000.50',
      liabilities_breakdown: { short_term: '9' },
      assets_breakdown: { stocks: '77.7' },
      quick_stats: { next_loan_date: '  ' },
    });

    const result = await dashboardApi.getGlobalSummary();
    expect(result.net_worth).toBe(1000.5);
    expect(result.liabilities_breakdown.long_term).toBe(0);
    expect(result.assets_breakdown.stocks).toBe(77.7);
    expect(result.quick_stats.next_loan_date).toBeNull();

    getMock.mockResolvedValueOnce(null);
    await expect(dashboardApi.getGlobalSummary()).resolves.toEqual(EMPTY_GLOBAL_SUMMARY);
  });

  it('maps current month dividends payload and defaults for invalid data', async () => {
    const { dashboardApi } = await import('./api_dashboard');

    getMock.mockResolvedValueOnce({
      received_this_month: '234.50',
      expected_this_month: '180.00',
      month_label: 'Kwiecień 2026',
      top_payers: [{ ticker: 'DNP.WA', amount: '120', date: '2026-04-15' }],
    });

    const result = await dashboardApi.getCurrentMonthDividends();
    expect(result.received_this_month).toBe(234.5);
    expect(result.expected_this_month).toBe(180);
    expect(result.month_label).toBe('Kwiecień 2026');
    expect(result.top_payers).toEqual([{ ticker: 'DNP.WA', amount: 120, date: '2026-04-15' }]);

    getMock.mockResolvedValueOnce(null);
    await expect(dashboardApi.getCurrentMonthDividends()).resolves.toEqual({
      received_this_month: 0,
      expected_this_month: 0,
      month_label: '',
      top_payers: [],
    });
  });
});
