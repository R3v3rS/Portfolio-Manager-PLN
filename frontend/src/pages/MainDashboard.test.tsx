import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MainDashboard from './MainDashboard';
import { dashboardApi } from '../api_dashboard';
import { portfolioApi } from '../api';
import { vi } from 'vitest';

vi.mock('../api_dashboard', async () => {
  const actual = await vi.importActual<typeof import('../api_dashboard')>('../api_dashboard');
  return {
    ...actual,
    dashboardApi: {
      getGlobalSummary: vi.fn(),
      getCurrentMonthDividends: vi.fn(),
    },
  };
});

vi.mock('../api', () => ({
  portfolioApi: {
    list: vi.fn(),
    getHoldings: vi.fn(),
  },
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: unknown }) => <div>{children as never}</div>,
  PieChart: ({ children }: { children: unknown }) => <div>{children as never}</div>,
  Pie: ({ children }: { children: unknown }) => <div>{children as never}</div>,
  Cell: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
}));

const mockedGetGlobalSummary = vi.mocked(dashboardApi.getGlobalSummary);
const mockedGetCurrentMonthDividends = vi.mocked(dashboardApi.getCurrentMonthDividends);
const mockedListPortfolios = vi.mocked(portfolioApi.list);
const mockedGetHoldings = vi.mocked(portfolioApi.getHoldings);

describe('MainDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetCurrentMonthDividends.mockResolvedValue({
      received_this_month: 234.5,
      expected_this_month: 180,
      month_label: 'Kwiecień 2026',
      top_payers: [{ ticker: 'DNP.WA', amount: 120, date: '2026-04-15' }],
    });
    mockedListPortfolios.mockResolvedValue({ portfolios: [] } as never);
    mockedGetHoldings.mockResolvedValue([]);
  });

  it('renders loading state before data is loaded', async () => {
    mockedGetGlobalSummary.mockReturnValue(new Promise(() => undefined));
    mockedListPortfolios.mockResolvedValue({ portfolios: [] });
    mockedGetHoldings.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <MainDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText('Ładowanie kokpitu...')).toBeInTheDocument();
  });

  it('renders KPI cards, chart section and formatted values after successful load', async () => {
    mockedGetGlobalSummary.mockResolvedValue({
      net_worth: 0,
      total_assets: 1234567.89,
      total_liabilities: 150000,
      liabilities_breakdown: { short_term: 50000, long_term: 100000 },
      assets_breakdown: {
        budget_cash: 50000,
        invest_cash: 250000,
        savings: 100000,
        bonds: 150000,
        stocks: 684567.89,
        ppk: 0,
      },
      quick_stats: {
        free_pool: 76543.21,
        next_loan_installment: 1234.56,
        next_loan_date: '2026-03-15',
      },
    });
    mockedListPortfolios.mockResolvedValue({
      portfolios: [{ id: 1, account_type: 'STANDARD' }],
    } as never);
    mockedGetHoldings.mockResolvedValue([
      { id: 1, portfolio_id: 1, ticker: 'CDR.WA', quantity: 1, average_buy_price: 100, total_cost: 100, current_value: 123.45, change_1d_percent: 3.24 },
    ] as never);

    render(
      <MemoryRouter>
        <MainDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: 'Pulpit Dowódcy' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Aktywa' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Zobowiązania' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Struktura Aktywów' })).toBeInTheDocument();
    expect((await screen.findAllByText(/1.*567,89 PLN/)).length).toBeGreaterThan(0);
    expect(await screen.findByText(/76.*543,21/)).toBeInTheDocument();
    expect(await screen.findByText('Termin: 15.03.2026')).toBeInTheDocument();
    expect(await screen.findByText('Dywidendy — Kwiecień 2026')).toBeInTheDocument();
    expect(await screen.findByText(/Otrzymane: 234,50 PLN/)).toBeInTheDocument();
    expect(await screen.findByText(/💰 DNP.WA 120,00 PLN/i)).toBeInTheDocument();
    expect(await screen.findByText('Dzisiejsze ruchy')).toBeInTheDocument();
    expect((await screen.findAllByText('CDR.WA')).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /Zarządzaj Portfelami/ })).toBeInTheDocument();
  });

  it('renders empty-style quick stat message when there is no upcoming installment', async () => {
    mockedGetGlobalSummary.mockResolvedValue({
      net_worth: 0,
      total_assets: 0,
      total_liabilities: 0,
      liabilities_breakdown: { short_term: 0, long_term: 0 },
      assets_breakdown: {
        budget_cash: 0,
        invest_cash: 0,
        savings: 0,
        bonds: 0,
        stocks: 0,
        ppk: 0,
      },
      quick_stats: {
        free_pool: 0,
        next_loan_installment: 0,
        next_loan_date: null,
      },
    });
    mockedGetCurrentMonthDividends.mockResolvedValue({
      received_this_month: 0,
      expected_this_month: 0,
      month_label: 'Kwiecień 2026',
      top_payers: [],
    });
    mockedListPortfolios.mockResolvedValue({ portfolios: [{ id: 1, account_type: 'STANDARD' }] } as never);
    mockedGetHoldings.mockResolvedValue([
      { id: 1, portfolio_id: 1, ticker: 'AAA', quantity: 1, average_buy_price: 100, total_cost: 100, current_value: 100, change_1d_percent: 0 },
    ] as never);

    render(
      <MemoryRouter>
        <MainDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText('Brak nadchodzących rat')).toBeInTheDocument();
    expect(await screen.findByText('Brak dywidend w tym miesiącu')).toBeInTheDocument();
    expect(await screen.findByText('Brak danych zmian dziennych')).toBeInTheDocument();
  });

  it('hides dividends widget when dividends endpoint fails', async () => {
    mockedGetGlobalSummary.mockResolvedValue({
      net_worth: 0,
      total_assets: 1000,
      total_liabilities: 0,
      liabilities_breakdown: { short_term: 0, long_term: 0 },
      assets_breakdown: {
        budget_cash: 1000,
        invest_cash: 0,
        savings: 0,
        bonds: 0,
        stocks: 0,
        ppk: 0,
      },
      quick_stats: {
        free_pool: 0,
        next_loan_installment: 0,
        next_loan_date: null,
      },
    });
    mockedGetCurrentMonthDividends.mockRejectedValue(new Error('endpoint down'));
    mockedListPortfolios.mockResolvedValue({ portfolios: [] } as never);

    render(
      <MemoryRouter>
        <MainDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: 'Pulpit Dowódcy' })).toBeInTheDocument();
    expect(screen.queryByText(/Dywidendy —/)).not.toBeInTheDocument();
  });

  it('renders error state when API request fails', async () => {
    mockedGetGlobalSummary.mockRejectedValue(new Error('Błąd pobierania dashboardu'));
    mockedListPortfolios.mockResolvedValue({ portfolios: [] });
    mockedGetHoldings.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <MainDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText('Błąd pobierania dashboardu')).toBeInTheDocument();
  });
});
