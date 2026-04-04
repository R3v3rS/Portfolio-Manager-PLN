import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock('./apiConfig', () => ({
  createApiClient: () => ({ get: getMock, post: postMock, delete: vi.fn() }),
}));

describe('api_loans', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('maps getLoans response and falls back to empty array', async () => {
    const { getLoans } = await import('./api_loans');
    getMock.mockResolvedValueOnce([{ id: '5', name: 'Hipoteka', original_amount: '200000' }]);

    await expect(getLoans()).resolves.toEqual([
      expect.objectContaining({ id: 5, name: 'Hipoteka', original_amount: 200000, duration_months: 0 }),
    ]);

    getMock.mockResolvedValueOnce({ items: [] });
    await expect(getLoans()).resolves.toEqual([]);
  });

  it('serializes schedule query params and normalizes nested schedule shape', async () => {
    const { getSchedule } = await import('./api_loans');
    getMock.mockResolvedValueOnce({
      loan: { id: '7', name: 'Kredyt', initial_rate: '5.7' },
      baseline: { total_interest: '1000', schedule: [{ month: '1', overpayment_type: 'UNKNOWN' }] },
      simulation: { total_interest: '900' },
      actual_metrics: { interest_saved: '100', months_saved: '2' },
      simulated_metrics: {},
      overpayments_list: null,
    });

    const result = await getSchedule(7, { sim_amount: 1234, simulated_action: 'REDUCE_TERM' });
    expect(getMock).toHaveBeenCalledWith('/7/schedule', {
      params: { sim_amount: 1234, simulated_action: 'REDUCE_TERM' },
    });
    expect(result.loan.initial_rate).toBe(5.7);
    expect(result.baseline.schedule[0].overpayment_type).toBeNull();
    expect(result.simulation.schedule).toEqual([]);
    expect(result.overpayments_list).toEqual([]);
  });

  it('sends createLoan body unchanged', async () => {
    const { createLoan } = await import('./api_loans');
    postMock.mockResolvedValueOnce({ message: 'ok' });

    await createLoan({
      name: 'Nowy',
      original_amount: 1000,
      duration_months: 12,
      start_date: '2026-01-01',
      installment_type: 'EQUAL',
      initial_rate: 6.2,
      category: 'HOME',
    });

    expect(postMock).toHaveBeenCalledWith('/', {
      name: 'Nowy',
      original_amount: 1000,
      duration_months: 12,
      start_date: '2026-01-01',
      installment_type: 'EQUAL',
      initial_rate: 6.2,
      category: 'HOME',
    });
  });
});
