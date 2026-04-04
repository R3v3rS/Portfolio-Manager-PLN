import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MainDashboard from './MainDashboard';
import { dashboardApi } from '../api_dashboard';
import { vi } from 'vitest';

vi.mock('../api_dashboard', async () => {
  const actual = await vi.importActual<typeof import('../api_dashboard')>('../api_dashboard');
  return {
    ...actual,
    dashboardApi: {
      getGlobalSummary: vi.fn(),
    },
  };
});

vi.mock('../components/AuditConsistencyPanel', () => ({
  default: () => <section>Audit Panel</section>,
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

describe('MainDashboard', () => {
  it('renders loading state before data is loaded', async () => {
    mockedGetGlobalSummary.mockReturnValue(new Promise(() => undefined));

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

    render(
      <MemoryRouter>
        <MainDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText('Brak nadchodzących rat')).toBeInTheDocument();
  });

  it('renders error state when API request fails', async () => {
    mockedGetGlobalSummary.mockRejectedValue(new Error('Błąd pobierania dashboardu'));

    render(
      <MemoryRouter>
        <MainDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText('Błąd pobierania dashboardu')).toBeInTheDocument();
  });
});
