import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { actionsApi, type ActionsWorkspace, type DashboardAction } from '../../api_actions';
import DashboardActions from './DashboardActions';

vi.mock('../../api_actions', () => ({ actionsApi: { get: vi.fn(), create: vi.fn(), update: vi.fn(), complete: vi.fn() } }));
const journal: DashboardAction = { key: 'journal:1', source: 'journal', category: 'investments', title: 'Przejrzyj tezę: ETF', description: 'Dodaj przegląd', due_date: '2026-10-01', href: '/journal?entry=1', action_label: 'Dodaj przegląd', amount: null, priority: 'normal', timing: 'overdue' };
const task: DashboardAction = { key: 'manual:3', task_id: 3, version: 1, source: 'manual', category: 'other', title: 'Sprawdź opłaty', description: 'Tabela bankowa', due_date: '2026-10-02', href: null, action_label: null, amount: null, priority: 'high', timing: 'today', completed_at: null };
const bill: DashboardAction = { key: 'bill:2:2026-10', source: 'bill', category: 'budget', title: 'Rozlicz rachunek: Internet', description: 'Bank', due_date: '2026-10-08', href: '/budget?view=bills&month=2026-10&bill=2', action_label: 'Rozlicz rachunek', amount: 80, priority: 'normal', timing: 'upcoming' };
const workspace = (): ActionsWorkspace => ({ as_of: '2026-10-02', horizon: '2026-11-01', items: [journal, task, bill], completed: [], stats: { open: 3, overdue: 1, today: 1, week: 2, completed: 0 }, warnings: [] });
const show = () => render(<MemoryRouter><DashboardActions/></MemoryRouter>);
const get = vi.mocked(actionsApi.get);

beforeEach(() => {
  vi.resetAllMocks(); get.mockResolvedValue(workspace());
  vi.mocked(actionsApi.create).mockResolvedValue({ id: 4 });
  vi.mocked(actionsApi.update).mockResolvedValue({ id: 3 });
  vi.mocked(actionsApi.complete).mockResolvedValue({ id: 3 });
});

describe('Dashboard action centre', () => {
  it('keeps four actions visible initially and allows opening the remaining list', async () => {
    get.mockResolvedValue({...workspace(),items:Array.from({length:9},(_,i) => ({...bill,key:`bill:${i}`,title:`Rachunek ${i}`}))});
    show(); await screen.findByText('Rachunek 0');
    expect(screen.getByText('Rachunek 3')).toBeInTheDocument();
    expect(screen.queryByText('Rachunek 4')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Pokaż kolejne sprawy (5)'}));
    expect(screen.getByText('Rachunek 8')).toBeInTheDocument();
  });
  it('shows source links and filters without offering completion of automatic financial actions', async () => {
    show(); await screen.findByText(journal.title);
    expect(screen.getByRole('link', { name: 'Dodaj przegląd' })).toHaveAttribute('href', '/journal?entry=1');
    expect(screen.getByRole('link', { name: 'Rozlicz rachunek' })).toHaveAttribute('href', bill.href);
    expect(screen.getAllByRole('button', { name: 'Wykonane' })).toHaveLength(2); // filter + personal task
    const nav = screen.getByRole('navigation', { name: 'Zakres spraw' });
    fireEvent.click(within(nav).getByRole('button', { name: 'Po terminie' }));
    expect(screen.getByText(journal.title)).toBeInTheDocument(); expect(screen.queryByText(task.title)).not.toBeInTheDocument();
    fireEvent.click(within(nav).getByRole('button', { name: '7 dni' }));
    expect(screen.queryByText(journal.title)).not.toBeInTheDocument(); expect(screen.getByText(bill.title)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Obszar spraw'), { target: { value: 'budget' } });
    expect(screen.queryByText(task.title)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Szukaj sprawy'), { target: { value: 'INTERNET' } });
    expect(screen.getByText(bill.title)).toBeInTheDocument();
    expect(actionsApi.complete).not.toHaveBeenCalled();
  });

  it('saves a personal task with a stable retry identifier and preserves drafts after an error', async () => {
    vi.mocked(actionsApi.create).mockRejectedValueOnce(new Error('Błąd zapisu'));
    show(); await screen.findByText(task.title); fireEvent.click(screen.getByRole('button', { name: 'Dodaj zadanie' }));
    fireEvent.change(screen.getByLabelText('Tytuł zadania'), { target: { value: 'Sprawdź dokumenty' } });
    fireEvent.change(screen.getByLabelText('Opis i następny krok'), { target: { value: 'Przeczytaj zestawienie opłat' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zadanie' }));
    await screen.findByText('Błąd zapisu'); expect(screen.getByLabelText('Tytuł zadania')).toHaveValue('Sprawdź dokumenty');
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zadanie' }));
    await waitFor(() => expect(screen.queryByRole('form', { name: 'Nowe zadanie' })).not.toBeInTheDocument());
    const calls = vi.mocked(actionsApi.create).mock.calls;
    expect(calls[0][1]).toBe(calls[1][1]);
    expect(calls[1][0]).toMatchObject({ title: 'Sprawdź dokumenty', notes: 'Przeczytaj zestawienie opłat', due_date: null });
  });

  it('does not repeat creation when refreshing the saved list fails', async () => {
    get.mockResolvedValueOnce(workspace()).mockRejectedValue(new Error('Błąd odczytu'));
    show(); await screen.findByText(task.title); fireEvent.click(screen.getByRole('button', { name: 'Dodaj zadanie' }));
    fireEvent.change(screen.getByLabelText('Tytuł zadania'), { target: { value: 'New task' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zadanie' }));
    await screen.findByRole('alert'); expect(screen.queryByRole('form')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }));
    await waitFor(() => expect(get).toHaveBeenCalledTimes(3)); expect(actionsApi.create).toHaveBeenCalledTimes(1);
  });

  it('moves confirmed completion to history and restores a personal task', async () => {
    const done = { ...task, version: 2, completed_at: '2026-10-02T10:00:00+00:00' };
    get.mockResolvedValueOnce(workspace()).mockResolvedValueOnce({ ...workspace(), items: [journal, bill], completed: [done], stats: { ...workspace().stats, completed: 1 } }).mockResolvedValue(workspace());
    show(); await screen.findByText(task.title);
    fireEvent.click(within(screen.getByText(task.title).closest('article')!).getByRole('button', { name: 'Wykonane' }));
    await screen.findByText('Zadanie wykonane. Znajdziesz je w historii.');
    await waitFor(() => expect(screen.queryByText(task.title)).not.toBeInTheDocument());
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Zakres spraw' })).getByRole('button', { name: 'Wykonane' }));
    await screen.findByText(task.title); fireEvent.click(screen.getByRole('button', { name: 'Przywróć' }));
    await screen.findByText('Zadanie przywrócone.');
    expect(actionsApi.complete).toHaveBeenNthCalledWith(1, 3, true, 1);
    expect(actionsApi.complete).toHaveBeenNthCalledWith(2, 3, false, 2);
  });

  it('retains unsaved edits on a version conflict', async () => {
    vi.mocked(actionsApi.update).mockRejectedValue(new Error('Zadanie zmieniło się w innej karcie'));
    show(); await screen.findByText(task.title);
    fireEvent.click(screen.getByRole('button', { name: `Edytuj zadanie: ${task.title}` }));
    fireEvent.change(screen.getByLabelText('Opis i następny krok'), { target: { value: 'Moja niezapisana poprawka' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz zadanie' }));
    await screen.findByRole('alert'); expect(screen.getByLabelText('Opis i następny krok')).toHaveValue('Moja niezapisana poprawka');
    expect(actionsApi.update).toHaveBeenCalledWith(3, expect.objectContaining({ notes: 'Moja niezapisana poprawka' }), 1);
  });

  it('shows an unavailable state instead of claiming there are no tasks when loading fails', async () => {
    get.mockRejectedValue(new Error('Serwer niedostępny'));
    show(); await screen.findByText('Serwer niedostępny');
    expect(screen.getByText('Lista spraw jest chwilowo niedostępna.')).toBeInTheDocument();
    expect(screen.queryByText('Nie ma teraz spraw do załatwienia')).not.toBeInTheDocument();
  });
});
