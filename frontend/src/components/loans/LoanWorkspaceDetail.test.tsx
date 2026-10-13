import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LoanWorkspaceDetail from './LoanWorkspaceDetail';
import { recordInstallment } from '../../api_loans';

const api = vi.hoisted(() => ({ getSchedule: vi.fn(), setLoanNetWorthExclusion: vi.fn(), getLoanPaymentCandidates:vi.fn(), saveLoanBudgetSettings:vi.fn() }));
vi.mock('../../api_loans', () => ({ ...api, addOverpayment: vi.fn(), addRate: vi.fn(), deleteInstallment: vi.fn(), deleteOverpayment: vi.fn(), recordBalanceCheck: vi.fn(), recordInstallment: vi.fn() }));
vi.mock('../../api_budget_workspace', () => ({ budgetWorkspaceApi: { get: async () => ({ accounts: [{id:1,name:'PKO',balance:1000,currency:'PLN'},{id:2,name:'Alior',balance:500,currency:'PLN'}],categories:[{id:10,name:'Opłaty'},{id:11,name:'Transport'}] }) } }));
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
  beforeEach(() => { cleanup(); vi.clearAllMocks(); api.getSchedule.mockResolvedValue(schedule()); api.getLoanPaymentCandidates.mockResolvedValue({items:[]}); });
  it('links an existing payment with its saved date and amount and previews the account debit',async()=>{
    api.getSchedule.mockResolvedValue({...schedule(),payments_list:[{id:2,installment_month:1,due_date:'2026-01-15',paid_on:'2026-01-13',amount:77.68,budget_linked:false}]});
    vi.mocked(recordInstallment).mockResolvedValue({id:2,budget_entry_id:8});
    show();await screen.findByRole('button',{name:'Historia i dane'});
    fireEvent.click(screen.getByRole('button',{name:'Historia i dane'}));
    expect(screen.getByText(/bez wydatku w budżecie/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Rozlicz w budżecie'}));
    const submit=screen.getByRole('button',{name:'Pomniejsz saldo i rozlicz'});
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Konto płatności'),{target:{value:'1'}});
    expect(screen.getByText(/→/)).toHaveTextContent(/922,32/);
    await waitFor(()=>expect(submit).toBeEnabled());
    fireEvent.click(submit);
    await waitFor(()=>expect(recordInstallment).toHaveBeenCalledWith(22,{installment_month:1,paid_on:'2026-01-13',amount:77.68,account_id:1,apply_to_budget:true,payment_id:2}));
  });
  it('links a bank expense without a second account debit and blocks an accidental duplicate',async()=>{
    api.getSchedule.mockResolvedValue({...schedule(),payments_list:[{id:2,installment_month:1,due_date:'2026-01-15',paid_on:'2026-01-13',amount:77.68,budget_linked:false}]});
    api.getLoanPaymentCandidates.mockResolvedValue({items:[{id:8,date:'2026-01-13',description:'Przelew z banku',amount:77.68,version:3,account_id:1,cash_effect:1}]});
    vi.mocked(recordInstallment).mockResolvedValue({id:2,budget_entry_id:8});
    show();fireEvent.click(await screen.findByRole('button',{name:'Historia i dane'}));
    fireEvent.click(screen.getByRole('button',{name:'Rozlicz w budżecie'}));
    fireEvent.change(screen.getByLabelText('Konto płatności'),{target:{value:'1'}});
    await screen.findByText(/Znaleziono 1 możliwych płatności/);
    expect(screen.getByRole('button',{name:'Pomniejsz saldo i rozlicz'})).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Powiązanie raty z wydatkiem'),{target:{value:'8'}});
    expect(screen.getByText(/→/)).toHaveTextContent(/1\s?000,00.*1\s?000,00/);
    fireEvent.click(screen.getByRole('button',{name:'Powiąż bez zmiany salda'}));
    await waitFor(()=>expect(recordInstallment).toHaveBeenCalledWith(22,{installment_month:1,paid_on:'2026-01-13',amount:77.68,account_id:1,apply_to_budget:true,payment_id:2,existing_entry_id:8,entry_version:3}));
  });
  it('saves the account and category separately for a loan',async()=>{
    api.getSchedule.mockResolvedValue({...schedule(),budget_settings:{loan_id:22,account_id:2,resolved_account_id:2,category_id:10,version:4}});
    api.saveLoanBudgetSettings.mockResolvedValue({loan_id:22,account_id:1,resolved_account_id:1,category_id:11,version:5});
    show();fireEvent.click(await screen.findByText('Budżet tego kredytu · konto i kategoria rat'));
    const account=screen.getByLabelText('Domyślne konto rat kredytu');
    expect(account).toHaveValue('2');
    fireEvent.change(account,{target:{value:'1'}});
    fireEvent.change(screen.getByLabelText('Kategoria rat kredytu'),{target:{value:'11'}});
    fireEvent.click(screen.getByRole('button',{name:'Zapisz konto i kategorię rat'}));
    await waitFor(()=>expect(api.saveLoanBudgetSettings).toHaveBeenCalledWith(22,{account_id:1,category_id:11,version:4}));
  });
  it('opens the next installment with its own account instead of an old unconfirmed row',async()=>{
    const oldRow={month:1,date:'2026-01-15',installment:77.68,interest_rate:0,remaining_balance:1000};
    const nextRow={...oldRow,month:11,date:'2026-11-15'};
    api.getSchedule.mockResolvedValue({...schedule(),actual:{schedule:[oldRow,nextRow]},status:{...schedule().status,next_due_date:'2026-11-15',next_installment:77.68},budget_settings:{loan_id:22,account_id:2,resolved_account_id:2,category_id:10,version:1}});
    show();fireEvent.click(await screen.findByRole('button',{name:'Zapisz spłatę'}));
    expect(screen.getByText('Rata 11')).toBeInTheDocument();
    expect(screen.getByLabelText('Konto budżetowe')).toHaveValue('2');
    await waitFor(()=>expect(api.getLoanPaymentCandidates).toHaveBeenCalledWith(22,2,expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),77.68));
  });
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
