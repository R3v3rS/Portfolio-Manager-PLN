import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { monthlyReportApi, type MonthlyReportData } from '../api_monthly_report';
import MonthlyReport from './MonthlyReport';

vi.mock('../api_monthly_report', () => ({ monthlyReportApi: { get: vi.fn() } }));
const budget = { income:1000,expenses:300,net:700,transfer_to_investments:200,transfer_from_investments:0,
  entry_count:3,receipt_count:1,planned:250,categories:[{id:1,name:'Jedzenie',planned:250,spent:300,difference:-50}] };
const fixture = (): MonthlyReportData => ({ schema_version:1,month:'2026-09',generated_at:'2026-10-02T12:00:00Z',
  period:{start:'2026-09-01',end:'2026-09-30',partial:false,previous_start:'2026-08-01',previous_end:'2026-08-31'},
  budget:{...budget,previous:{...budget,income:900,expenses:250,net:650},changes:{income:100,expenses:50,net:50}},
  investments:{operations:{count:2,buys:1,sells:0,deposits:200,withdrawals:0,internal_transfers:0,dividends:10,interest:0,commissions:1,realized_profit:0},
    performance:{profit:null,complete:false,excluded_count:0,archived_count:0,items:[{id:1,name:'IKE',account_type:'IKE',opening_value:1000,closing_value:null,profit:null,return_percent:null,status:'partial',warnings:['Brak pełnej wyceny granic okresu: ETF.']}]},
    ppk:{count:0,employee_contributions:0,employer_contributions:0}},
  loans:{paid_amount:100,overpaid_amount:50,without_record:1,items:[{id:22,name:'Kredyt',scheduled_count:1,scheduled_amount:100,without_record:1,estimated_balance:1000,paid_count:1,paid_amount:100,overpaid_amount:50,budget_linked_amount:100}]},
  wealth:{opening:null,closing:null,latest:null,change:null,observations:0},
  journal:{entries:[],reviews:[{id:1,entry_id:7,review_date:'2026-09-20',outcome:'CONFIRMED',notes:'Teza pozostaje aktualna.',lessons:'Sprawdzaj koszty.',title:'Teza ETF',ticker:'ETF'}],due:[]},
  completed_tasks:[{id:3,title:'Przeczytaj zestawienie opłat',category:'investments',completed_at:'2026-09-15T12:00:00Z'}],
  insights:[{tone:'attention',text:'Sprawdź plan wydatków.',href:'/budget?month=2026-09&view=plan',label:'Sprawdź plan'}],
  warnings:['Brak zapisanej wyceny całego majątku na obu granicach okresu.'] });
const get = vi.mocked(monthlyReportApi.get);
const show = (url='/reports/monthly?month=2026-09') => render(<MemoryRouter initialEntries={[url]}><MonthlyReport/></MemoryRouter>);

beforeEach(() => { vi.resetAllMocks(); get.mockResolvedValue(fixture()); });
afterEach(() => { vi.restoreAllMocks(); });

describe('Monthly report', () => {
  it('shows recorded finances, missing valuations, review lessons and actionable links', async () => {
    show(); await screen.findByRole('heading',{name:'wrzesień 2026'});
    expect(screen.getByText('Brak pełnej wyceny granic okresu: ETF.')).toBeInTheDocument();
    const kpis=screen.getByRole('region',{name:'Podsumowanie miesiąca'});
    expect(within(kpis).getByText('Wynik inwestycji').closest('article')).toHaveTextContent('—');
    expect(screen.getByText('Sprawdzaj koszty.')).toBeInTheDocument();
    expect(screen.getByText('Przeczytaj zestawienie opłat')).toBeInTheDocument();
    expect(screen.getByRole('link',{name:'Sprawdź plan'})).toHaveAttribute('href','/budget?month=2026-09&view=plan');
    expect(screen.getByRole('link',{name:'Teza ETF'})).toHaveAttribute('href','/journal?entry=7');
    expect(screen.getByText(/nie są dodawane drugi raz/)).toBeInTheDocument();
  });

  it('labels the partial month and the actual comparison interval', async () => {
    get.mockResolvedValue({...fixture(),month:'2026-10',period:{start:'2026-10-01',end:'2026-10-02',partial:true,previous_start:'2026-09-01',previous_end:'2026-09-02'}});
    show('/reports/monthly?month=2026-10');
    await screen.findByText('Miesiąc w toku');
    expect(screen.getByText(/tym samym fragmentem poprzedniego miesiąca/)).toBeInTheDocument();
    expect(screen.getByText(/Porównanie:.*1 wrz 2026.*2 wrz 2026/)).toBeInTheDocument();
  });

  it('clears the old report and disables export and print while another month loads', async () => {
    get.mockResolvedValueOnce(fixture()).mockImplementationOnce(() => new Promise(() => {}));
    show(); await screen.findByRole('heading',{name:'wrzesień 2026'});
    fireEvent.click(screen.getByRole('button',{name:'Poprzedni miesiąc'}));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith('2026-08'));
    expect(screen.getByRole('button',{name:'Eksport JSON'})).toBeDisabled();
    expect(screen.getByRole('button',{name:'Drukuj / PDF'})).toBeDisabled();
    expect(screen.queryByRole('heading',{name:'wrzesień 2026'})).not.toBeInTheDocument();
  });

  it('ignores a late response from the previously selected month', async () => {
    let resolveFirst!: (value: MonthlyReportData) => void;
    get.mockImplementationOnce(() => new Promise(resolve => { resolveFirst=resolve; })).mockResolvedValueOnce({...fixture(),month:'2026-08',period:{...fixture().period,start:'2026-08-01',end:'2026-08-31'}});
    show(); fireEvent.click(screen.getByRole('button',{name:'Poprzedni miesiąc'}));
    await screen.findByRole('heading',{name:'sierpień 2026'});
    await act(async () => { resolveFirst(fixture()); });
    expect(screen.getByRole('heading',{name:'sierpień 2026'})).toBeInTheDocument();
    expect(screen.queryByRole('heading',{name:'wrzesień 2026'})).not.toBeInTheDocument();
  });

  it('reports fetch failure and retries instead of displaying a zero report', async () => {
    get.mockRejectedValueOnce(new Error('Raport niedostępny')).mockResolvedValueOnce(fixture());
    show(); await screen.findByRole('alert');
    expect(screen.getByRole('button',{name:'Drukuj / PDF'})).toBeDisabled();
    fireEvent.click(screen.getByRole('button',{name:'Spróbuj ponownie'}));
    await screen.findByRole('heading',{name:'wrzesień 2026'});
    expect(get).toHaveBeenCalledTimes(2);
  });

  it('prints the loaded report and bounds calendar navigation', async () => {
    const print=vi.spyOn(window,'print').mockImplementation(() => {});
    show(); await screen.findByRole('heading',{name:'wrzesień 2026'});
    fireEvent.click(screen.getByRole('button',{name:'Drukuj / PDF'})); expect(print).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText('Miesiąc raportu'),{target:{value:'2000-01'}});
    await waitFor(() => expect(get).toHaveBeenLastCalledWith('2000-01'));
    expect(screen.getByRole('button',{name:'Poprzedni miesiąc'})).toBeDisabled();
  });
});
