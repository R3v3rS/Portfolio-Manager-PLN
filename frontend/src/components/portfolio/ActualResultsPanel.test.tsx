import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ActualResultsPanel from './ActualResultsPanel';
import { actualResultsApi, type ActualResults } from '../../api_actual_results';

vi.mock('../../api_actual_results', () => ({ actualResultsApi: { portfolio: vi.fn(), goal: vi.fn() } }));
const result: ActualResults = {
  from:'2025-01-01',to:'2026-10-02',currency:'PLN',status:'ok',portfolio_names:['IKE'],
  opening_value:1000,closing_value:1350,deposits:500,withdrawals:200,net_deposits:300,profit:50,
  dietz_percent:4.4,xirr_percent:3,dividends:10,interest:2,realized_profit:20,modeled_interest:0,
  recorded_commissions:0,transaction_count:20,internal_transfer_amount:100,
  reconciliation:{cash_difference:0,positions_mismatch:[],consistent:true},
  months:[{date:'2026-10-02',opening_value:1300,closing_value:1350,net_deposits:0,profit:50,return_percent:3.8,partial_month:true,complete:true}],
  positive_months:1,known_months:1,best_month:null,worst_month:null,warnings:[],
};
beforeEach(() => {vi.clearAllMocks(); vi.mocked(actualResultsApi.portfolio).mockResolvedValue(result);vi.mocked(actualResultsApi.goal).mockResolvedValue(result);});
afterEach(() => {cleanup();vi.useRealTimers();});

describe('Actual investment results', () => {
  it('reconciles value with net deposits and profit without adding income a second time', async () => {
    render(<ActualResultsPanel portfolioId={1} from="2025-01-01" />);
    const bridge = await screen.findByLabelText('Rozliczenie zmiany wartości');
    expect(bridge).toHaveTextContent(/1\s?000,00/);expect(bridge).toHaveTextContent('300,00');expect(bridge).toHaveTextContent('50,00');expect(bridge).toHaveTextContent(/1\s?350,00/);
    expect(actualResultsApi.portfolio).toHaveBeenCalledWith(1,'2025-01-01');
    expect(screen.getByText(/Dywidendy i odsetki są już częścią wyniku/)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Wyniki miesiąc po miesiącu/));
    expect(within(screen.getByRole('table')).getByText(/część miesiąca/)).toBeInTheDocument();
  });
  it('requests the current goal scope and changes its analysis period', async () => {
    vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date('2026-10-02T12:00:00'));
    render(<ActualResultsPanel goalId={7} />);
    await screen.findByLabelText('Rozliczenie zmiany wartości');
    expect(actualResultsApi.goal).toHaveBeenCalledWith(7,undefined);
    fireEvent.change(screen.getByLabelText('Okres rzeczywistych wyników'),{target:{value:'3'}});
    await waitFor(() => expect(actualResultsApi.goal).toHaveBeenLastCalledWith(7,'2026-08-01'));
    expect(actualResultsApi.portfolio).not.toHaveBeenCalled();
    expect(screen.getByText(/również sprzed utworzenia celu/)).toBeInTheDocument();
  });
  it('shows inconsistencies and missing rates explicitly', async () => {
    vi.mocked(actualResultsApi.portfolio).mockResolvedValue({...result,status:'inconsistent',dietz_percent:null,xirr_percent:null,reconciliation:{cash_difference:20,positions_mismatch:['ABC'],consistent:false},warnings:['Saldo nie zgadza się z historią.']});
    render(<ActualResultsPanel portfolioId={1} />);
    expect(await screen.findByText('Saldo nie zgadza się z historią.')).toBeInTheDocument();
    expect(await screen.findByText('Wynik wymagający wyjaśnienia')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Jakość danych i sposób liczenia'));
    expect(screen.getByText(/Niezgodne pozycje: ABC/)).toBeInTheDocument();
  });
  it('retries a read failure and does not write financial data', async () => {
    vi.mocked(actualResultsApi.goal).mockRejectedValueOnce(new Error('Unavailable'));
    render(<ActualResultsPanel goalId={7} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się wczytać');
    fireEvent.click(screen.getByRole('button',{name:'Spróbuj ponownie'}));
    await screen.findByLabelText('Rozliczenie zmiany wartości');
    expect(actualResultsApi.goal).toHaveBeenCalledTimes(2);
  });
  it('does not display false financial zeros for an unsupported account model', async () => {
    vi.mocked(actualResultsApi.goal).mockResolvedValue({...result,status:'unsupported',warnings:['PPK wymaga odrębnej historii wyceny.']});
    render(<ActualResultsPanel goalId={7} />);
    expect(await screen.findByText('PPK wymaga odrębnej historii wyceny.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Rozliczenie zmiany wartości')).not.toBeInTheDocument();
  });
});
