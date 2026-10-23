import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { budgetWorkspaceApi, type BudgetWorkspace, type PlanTransferPreview } from '../../api_budget_workspace';
import { budgetImportsApi, type BudgetImportsWorkspace } from '../../api_budget_imports';
import { HttpError } from '../../http';
import BudgetPlanTransfer from './BudgetPlanTransfer';
import BudgetYearPlan from './BudgetYearPlan';
import BudgetReviewQueue from './BudgetReviewQueue';
import BudgetTransactions from './BudgetTransactions';
import BudgetTransactionRow from './BudgetTransactionRow';

vi.mock('../../api_budget_workspace', () => ({ budgetWorkspaceApi: {
  previewTransfer: vi.fn(), transferPlan: vi.fn(), yearPlan: vi.fn(), receiptUrl: () => '/receipt',
} }));
vi.mock('../../api_budget_imports', () => ({ budgetImportsApi: { get: vi.fn() } }));
const data = (): BudgetWorkspace => ({ month: '2030-01', accounts: [{ id: 1, name: 'Konto' }],
  categories: [{ id: 1, name: 'Jedzenie', planned: 500, remaining: 300 }, { id: 2, name: 'Transport', planned: 100, remaining: 100 }],
  entries: [{ id: 1, date: '2030-01-03', description: 'Zakupy', account_id: 1, account_name: 'Konto', kind: 'EXPENSE', amount: 100,
    has_receipt: false, classification_status: 'GENERAL', lines: [{ category_id: 1, category_name: 'Jedzenie', label: 'Produkt', amount: 100 }] }],
} as BudgetWorkspace);
const preview: PlanTransferPreview = { month: '2030-01', source_id: 1, target_id: 2, amount: 50, token: 'version-1',
  source_name: 'Jedzenie', target_name: 'Transport', source_before: 500, source_after: 450, target_before: 100,
  target_after: 150, total_before: 600, total_after: 600 };
const reload = vi.fn(async () => {}), close = vi.fn();
const show = (node: React.ReactNode) => render(<MemoryRouter>{node}</MemoryRouter>);
const fillTransfer = () => {
  fireEvent.change(screen.getByLabelText('Z której kategorii'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Do której kategorii'), { target: { value: '2' } });
  fireEvent.change(screen.getByLabelText('Kwota limitu (PLN)'), { target: { value: '50' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sprawdź podgląd' }));
};
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear();
  vi.mocked(budgetWorkspaceApi.previewTransfer).mockResolvedValue(preview);
  vi.mocked(budgetWorkspaceApi.transferPlan).mockResolvedValue(preview);
  vi.mocked(budgetImportsApi.get).mockResolvedValue({ pending_count: 0, sessions: [], receipts: [] } as unknown as BudgetImportsWorkspace);
});
afterEach(() => { cleanup(); document.body.style.overflow = ''; localStorage.clear(); });

it('requires a reviewed allowance move and repeats the same save after an uncertain response', async () => {
  vi.mocked(budgetWorkspaceApi.transferPlan).mockRejectedValueOnce(new Error('Brak odpowiedzi'));
  vi.mocked(budgetWorkspaceApi.previewTransfer).mockResolvedValue({...preview,related_limits:[{name:'Grupa',before:500,after:450}]});
  show(<BudgetPlanTransfer data={data()} reload={reload} onClose={close}/>); fillTransfer();
  const confirm = await screen.findByRole('button', { name: 'Zatwierdź przeniesienie' });
  expect(budgetWorkspaceApi.transferPlan).not.toHaveBeenCalled();
  expect(screen.getByText(/Wspólny limit Grupa/)).toHaveTextContent('500,00');
  expect(screen.getByLabelText('Podgląd przeniesienia limitu')).toHaveTextContent('600,00');
  fireEvent.click(confirm); await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Zatwierdź przeniesienie' }));
  await waitFor(() => expect(close).toHaveBeenCalledOnce());
  const calls = vi.mocked(budgetWorkspaceApi.transferPlan).mock.calls;
  expect(calls[0]).toEqual(calls[1]); expect(calls[0][1]).toBe('version-1');
  expect(reload).toHaveBeenCalledOnce();
});

it('invalidates a stale preview and any preview after editing the amount', async () => {
  vi.mocked(budgetWorkspaceApi.transferPlan).mockRejectedValueOnce(new HttpError('Plan się zmienił', 409));
  show(<BudgetPlanTransfer data={data()} reload={reload} onClose={close}/>); fillTransfer();
  fireEvent.click(await screen.findByRole('button', { name: 'Zatwierdź przeniesienie' }));
  await screen.findByRole('alert'); expect(screen.queryByLabelText('Podgląd przeniesienia limitu')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Sprawdź podgląd' }));
  await screen.findByLabelText('Podgląd przeniesienia limitu');
  fireEvent.change(screen.getByLabelText('Kwota limitu (PLN)'), { target: { value: '60' } });
  expect(screen.queryByRole('button', { name: 'Zatwierdź przeniesienie' })).not.toBeInTheDocument();
  expect(budgetWorkspaceApi.transferPlan).toHaveBeenCalledTimes(1);
});

it('loads the annual plan without saving and links to the exact month', async () => {
  vi.mocked(budgetWorkspaceApi.yearPlan).mockResolvedValue({ start: '2030-01', months: [{ month: '2030-01', income: 1000,
    ordinary: 600, payments: 200, reserves: 100, cost: 900, remaining: 100, spent: 0, carryover: 0,
    missing_plans: ['Zdrowie'], sources: [] }] });
  show(<BudgetYearPlan month="2030-01"/>);
  const table = await screen.findByRole('table'); expect(table).toHaveTextContent('Kategorie bez planu: 1');
  expect(within(table).getByRole('link')).toHaveAttribute('href', '/budget?view=plan&month=2030-01');
  expect(budgetWorkspaceApi.yearPlan).toHaveBeenCalledWith('2030-01');
  expect(budgetWorkspaceApi.transferPlan).not.toHaveBeenCalled();
});

it('refreshes an already saved move without sending it again after a failed refresh', async () => {
  reload.mockRejectedValueOnce(new Error('Brak odczytu')).mockResolvedValue(undefined);
  show(<BudgetPlanTransfer data={data()} reload={reload} onClose={close}/>); fillTransfer();
  fireEvent.click(await screen.findByRole('button', { name: 'Zatwierdź przeniesienie' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Limity zostały zapisane');
  expect(screen.getByLabelText('Kwota limitu (PLN)')).toBeDisabled();
  expect(close).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Odśwież plan' }));
  await waitFor(() => expect(close).toHaveBeenCalledOnce());
  expect(budgetWorkspaceApi.transferPlan).toHaveBeenCalledTimes(1);
  expect(reload).toHaveBeenCalledTimes(2);
});

it('saves a filter locally, restores it after remounting and excludes receipt purchases', () => {
  const view = show(<BudgetTransactions data={data()}>{row => <p key={row.id}>{row.description}</p>}</BudgetTransactions>);
  fireEvent.click(screen.getByText('Więcej filtrów i zapisane widoki'));
  fireEvent.change(screen.getByLabelText('Szukaj transakcji'), { target: { value: 'Zakupy' } });
  fireEvent.change(screen.getByLabelText('Powiązanie i stan'), { target: { value: 'NO_RECEIPT' } });
  fireEvent.change(screen.getByLabelText('Nazwa filtra'), { target: { value: 'Bez paragonów' } });
  fireEvent.click(screen.getByRole('button', { name: 'Zapisz filtr' })); view.unmount();
  const next = data(); next.entries.push({ ...next.entries[0], id: 2, has_receipt: true, description: 'Zakupy z paragonem' });
  show(<BudgetTransactions data={next}>{row => <p key={row.id}>{row.description}</p>}</BudgetTransactions>);
  fireEvent.click(screen.getByRole('button', { name: 'Bez paragonów' }));
  expect(screen.getByText('Zakupy', { exact: true })).toBeInTheDocument();
  expect(screen.queryByText('Zakupy z paragonem')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Szukaj transakcji')).toHaveValue('Zakupy');
  fireEvent.click(screen.getByRole('button', { name: 'Usuń filtr: Bez paragonów' }));
  expect(screen.queryByRole('button', { name: 'Bez paragonów' })).not.toBeInTheDocument();
});

it('opens the exact pending documents from the review queue and tolerates a failed import read', async () => {
  vi.mocked(budgetImportsApi.get).mockResolvedValueOnce({ pending_count: 1, sessions: [{ id: 7, filename: 'bank.csv', status: 'PENDING' }],
    receipts: [{ id: 8, filename: 'paragon.jpg', status: 'PENDING' }] } as unknown as BudgetImportsWorkspace);
  const view = show(<BudgetReviewQueue data={data()} forecast={null}/>);
  expect((await screen.findByText('Import: bank.csv')).closest('li')?.querySelector('a')).toHaveAttribute('href', '/budget/imports?tab=csv&session_id=7&month=2030-01');
  expect(screen.getByText('Paragon: paragon.jpg').closest('li')?.querySelector('a')).toHaveAttribute('href', '/budget/imports?tab=receipt&receipt_id=8&month=2030-01');
  fireEvent.change(screen.getByLabelText('Rodzaj spraw'), { target: { value: 'ACCOUNT' } });
  expect(screen.queryByText('Import: bank.csv')).not.toBeInTheDocument(); view.unmount();
  vi.mocked(budgetImportsApi.get).mockRejectedValueOnce(new Error('Nie działa'));
  show(<BudgetReviewQueue data={data()} forecast={null}/>);
  expect(await screen.findByRole('status')).toHaveTextContent('Nie udało się odczytać stanu importów');
});

it('opens the full purchase split and forwards refunds through its details', () => {
  const entry = data().entries[0]; const refund = vi.fn();
  show(<BudgetTransactionRow entry={entry} busy={false} edit={vi.fn()} apply={vi.fn()} refund={refund} remove={vi.fn()}/>);
  expect(screen.queryByRole('button', { name: 'Zapisz zwrot: Zakupy' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Szczegóły transakcji: Zakupy' }));
  const dialog = within(screen.getByRole('dialog')); expect(dialog.getByText('Produkt')).toBeInTheDocument();
  fireEvent.click(dialog.getByRole('button', { name: 'Zapisz zwrot: Zakupy' }));
  expect(refund).toHaveBeenCalledWith(entry); expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
