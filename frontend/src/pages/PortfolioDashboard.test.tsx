import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import PortfolioDashboard from './PortfolioDashboard';
import { portfolioApi } from '../api';
import { vi } from 'vitest';

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    portfolioApi: {
      list: vi.fn(),
      limits: vi.fn(),
      config: vi.fn(),
      create: vi.fn(),
      createChild: vi.fn(),
    },
  };
});

const mockedPortfolioApi = vi.mocked(portfolioApi);

const listResponse = {
  portfolios: [
    {
      id: 1,
      name: 'Portfel Główny',
      account_type: 'STANDARD' as const,
      current_cash: 5000,
      total_deposits: 10000,
      portfolio_value: 12345.67,
      total_dividends: 222.22,
      total_result: 2345.67,
      total_result_percent: 23.45,
      children: [],
    },
  ],
};

const limitsResponse = {
  limits: {
    year: 2026,
    IKE: { deposited: 5000, limit: 26000, percentage: 19.23 },
    IKZE: { deposited: 2000, limit: 12000, percentage: 16.67 },
  },
};

const configResponse = {
  subportfolios_allowed_types: ['STANDARD', 'IKE'],
};

describe('PortfolioDashboard', () => {
  beforeEach(() => {
    mockedPortfolioApi.list.mockResolvedValue(listResponse as never);
    mockedPortfolioApi.limits.mockResolvedValue(limitsResponse as never);
    mockedPortfolioApi.config.mockResolvedValue(configResponse as never);
    mockedPortfolioApi.create.mockResolvedValue({} as never);
    mockedPortfolioApi.createChild.mockResolvedValue({} as never);
  });

  it('renders loading state before data fetch resolves', async () => {
    mockedPortfolioApi.list.mockReturnValue(new Promise(() => undefined) as never);

    render(
      <MemoryRouter>
        <PortfolioDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText('Ładowanie...')).toBeInTheDocument();
  });

  it('renders KPI cards, tax limits and table rows after loading', async () => {
    render(
      <MemoryRouter>
        <PortfolioDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByRole('heading', { name: 'Inwestycje - Dashboard' })).toBeInTheDocument();
    expect(await screen.findByText('Wartość Portfeli')).toBeInTheDocument();
    expect((await screen.findAllByText('12345.67 PLN')).length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Limity Podatkowe (2026)' })).toBeInTheDocument();
    expect(await screen.findByText('5000.00 / 26000.00 PLN')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Portfel Główny/ })).toBeInTheDocument();
  });

  it('renders empty state when no portfolios exist', async () => {
    mockedPortfolioApi.list.mockResolvedValueOnce({ portfolios: [] } as never);

    render(
      <MemoryRouter>
        <PortfolioDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText('Brak portfeli. Utwórz nowy, aby rozpocząć!')).toBeInTheDocument();
  });

  it('renders error state when dashboard fetch fails', async () => {
    mockedPortfolioApi.list.mockRejectedValueOnce(new Error('Fetch failed'));

    render(
      <MemoryRouter>
        <PortfolioDashboard />
      </MemoryRouter>
    );

    expect(await screen.findByText('Failed to fetch dashboard data')).toBeInTheDocument();
  });

  it('submits create portfolio form and sends payload', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PortfolioDashboard />
      </MemoryRouter>
    );

    await screen.findByRole('heading', { name: 'Inwestycje - Dashboard' });

    await user.click(screen.getByRole('button', { name: 'Nowy Portfel' }));
    await user.type(screen.getByRole('textbox', { name: 'Nazwa Portfela' }), 'Nowy Portfel Testowy');
    await user.type(screen.getByRole('spinbutton', { name: 'Gotówka na start (PLN)' }), '1500');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Typ Konta' }), 'IKE');

    await user.click(screen.getByRole('button', { name: 'Utwórz Portfel' }));

    expect(mockedPortfolioApi.create).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Nowy Portfel Testowy',
        initial_cash: 1500,
        account_type: 'IKE',
      })
    );
  });
});
