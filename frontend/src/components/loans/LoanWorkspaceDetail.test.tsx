import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LoanWorkspaceDetail from './LoanWorkspaceDetail';

const api = vi.hoisted(() => ({ getSchedule: vi.fn(), setLoanNetWorthExclusion: vi.fn() }));
vi.mock('../../api_loans', () => ({ ...api, addOverpayment: vi.fn(), addRate: vi.fn(), deleteInstallment: vi.fn(), deleteOverpayment: vi.fn(), recordBalanceCheck: vi.fn(), recordInstallment: vi.fn() }));
vi.mock('../../api_budget_workspace', () => ({ budgetWorkspaceApi: { get: async () => ({ accounts: [] }) } }));
vi.mock('../charts/ChartKit', () => ({ TrendChart: () => null }));
vi.mock('./LoanPaymentChart', () => ({ default: () => null }));

const schedule = (excluded = false) => ({
  loan: { id: 22, name: 'Kredyt', category: 'GOTOWKOWY', start_date: '2026-01-01', installment_type: 'EQUAL', exclude_from_net_worth: excluded },
  actual: { schedule: [] }, baseline: { schedule: [] }, simulation: { schedule: [] },
  payments_list: [], rates_list: [], balance_checks_list: [], overpayments_list: [],
  actual_metrics: { interest_saved: 0, months_saved: 0 }, simulated_metrics: {},
  status: { estimated_balance: 1000, next_due_date: null, next_installment: 0, confirmed_balance: null, confirmed_on: null },
});
const show = () => render(<MemoryRouter initialEntries={['/loans/22']}><Routes><Route path="/loans/:id" element={<LoanWorkspaceDetail/>}/></Routes></MemoryRouter>);
describe('Loan net worth setting', () => {
  beforeEach(() => { cleanup(); vi.clearAllMocks(); api.getSchedule.mockResolvedValue(schedule()); });
  it('saves exclusion, restores it after loading and can include the loan again', async () => {
    api.setLoanNetWorthExclusion.mockResolvedValueOnce({ id: 22, exclude_from_net_worth: true });
    const page = show();
    const checkbox = await screen.findByRole('checkbox', { name: 'Nie uwzględniaj w majątku netto' });
    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    await waitFor(() => expect(checkbox).toBeChecked());
    expect(api.setLoanNetWorthExclusion).toHaveBeenCalledWith(22, true);
    expect(screen.getByRole('status')).toHaveTextContent('Raty pozostają');
    page.unmount(); api.getSchedule.mockResolvedValue(schedule(true)); show();
    const restored = await screen.findByRole('checkbox');
    expect(restored).toBeChecked();
    api.setLoanNetWorthExclusion.mockResolvedValueOnce({ id: 22, exclude_from_net_worth: false });
    fireEvent.click(restored);
    await waitFor(() => expect(restored).not.toBeChecked());
    expect(api.setLoanNetWorthExclusion).toHaveBeenLastCalledWith(22, false);
  });
  it('keeps the saved selection and allows retry when the save fails', async () => {
    api.setLoanNetWorthExclusion.mockRejectedValueOnce(new Error('Brak połączenia'));
    show();
    const checkbox = await screen.findByRole('checkbox');
    fireEvent.click(checkbox);
    expect(await screen.findByRole('alert')).toHaveTextContent('Brak połączenia');
    expect(checkbox).not.toBeChecked(); expect(checkbox).not.toBeDisabled();
    api.setLoanNetWorthExclusion.mockResolvedValueOnce({ id: 22, exclude_from_net_worth: true });
    fireEvent.click(checkbox);
    await waitFor(() => expect(checkbox).toBeChecked());
  });
});
