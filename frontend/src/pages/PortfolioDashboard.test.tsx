import { render, screen, waitFor, within } from '@testing-library/react';
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
      refreshPpkPrice: vi.fn(),
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
    vi.clearAllMocks();
    mockedPortfolioApi.refreshPpkPrice.mockResolvedValue({changed:false, warning:null, currentPrice:null});
    mockedPortfolioApi.list.mockResolvedValue(listResponse as never);
    mockedPortfolioApi.limits.mockResolvedValue(limitsResponse as never);
    mockedPortfolioApi.config.mockResolvedValue(configResponse as never);
    mockedPortfolioApi.create.mockResolvedValue({} as never);
    mockedPortfolioApi.createChild.mockResolvedValue({} as never);
  });

  it('refreshes a stale PPK quote and updates the totals without blocking the initial view', async () => {
    const old = {...listResponse.portfolios[0], id:5, name:'PPK NN', account_type:'PPK', asset_value:1000, portfolio_value:800};
    const updated = {...old, asset_value:1100, portfolio_value:900};
    mockedPortfolioApi.list.mockResolvedValueOnce({portfolios:[old]} as never).mockResolvedValue({portfolios:[updated]} as never);
    mockedPortfolioApi.refreshPpkPrice.mockResolvedValue({changed:true,warning:null,currentPrice:{price:27.09,date:'2026-10-01',source:'Nationale-Nederlanden'}});
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    await waitFor(() => expect(mockedPortfolioApi.refreshPpkPrice).toHaveBeenCalledWith(5));
    await waitFor(() => expect(screen.getByText('Wartość aktywów',{selector:'dt'}).closest('dl')).toHaveTextContent('1100,00'));
    expect(mockedPortfolioApi.refreshPpkPrice).toHaveBeenCalledTimes(1);
  });

  it('preserves the visible PPK totals and explains a refresh failure', async () => {
    mockedPortfolioApi.list.mockResolvedValue({portfolios:[{...listResponse.portfolios[0],account_type:'PPK'}]} as never);
    mockedPortfolioApi.refreshPpkPrice.mockRejectedValue(new Error('offline'));
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    expect(await screen.findByRole('status')).toHaveTextContent('Zachowano ostatnią zapisaną cenę');
    expect(screen.getByText('Wartość aktywów',{selector:'dt'}).closest('dl')).toHaveTextContent('12');
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

    expect(await screen.findByRole('heading', { name: 'Przegląd inwestycji' })).toBeInTheDocument();
    expect(await screen.findByText('Wartość aktywów', {selector:'dt'})).toBeInTheDocument();
    expect((await screen.findAllByText(/12.*345,67 PLN/)).length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Limity wpłat · 2026' })).toBeInTheDocument();
    expect(screen.getByText(/21.*000,00 PLN/)).toBeInTheDocument();
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

    expect(await screen.findByText('Nie udało się wczytać portfeli.')).toBeInTheDocument();
  });

  it('keeps portfolios visible when the tax limits section fails', async () => {
    mockedPortfolioApi.limits.mockRejectedValueOnce(new Error('Unavailable'));
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    expect(await screen.findByRole('link', {name: /Portfel Główny/})).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Limity wpłat są chwilowo niedostępne');
  });

  it('separates PPK assets, withdrawal and fund profit without adding children twice', async () => {
    mockedPortfolioApi.list.mockResolvedValueOnce({portfolios:[{...listResponse.portfolios[0], name:'PPK', account_type:'PPK',
      asset_value:1800, withdrawable_value:1568.7, net_contributions:1500, investment_result:300,
      children:[{...listResponse.portfolios[0],id:2,parent_portfolio_id:1,asset_value:500}]}]} as never);
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    await screen.findByText('Wartość aktywów', {selector:'dt'});
    expect(screen.getByText('Wartość aktywów', {selector:'dt'}).closest('dl')).toHaveTextContent(/1.*800,00/);
    expect(screen.getByText('Szacowana wypłata', {selector:'dt'}).closest('dl')).toHaveTextContent(/1.*568,70/);
    expect(screen.getByText('Wynik inwestowania', {selector:'dt'}).closest('dl')).toHaveTextContent('300,00');
  });

  it('does not present the incomplete subtotal as full value or zero profit', async () => {
    mockedPortfolioApi.list.mockResolvedValueOnce({portfolios:[{...listResponse.portfolios[0], valuation_status:'incomplete',
      portfolio_value:undefined,total_result:undefined,total_result_percent:undefined,available_value:50,
      valuation_warnings:['ABC: brak ceny.']}]} as never);
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    expect(await screen.findByRole('status')).toHaveTextContent('Niepełna wycena');
    expect(screen.getByText('Wartość aktywów', {selector:'dt'}).closest('dl')).toHaveTextContent('—');
    expect(screen.getByText('Wynik inwestowania', {selector:'dt'}).closest('dl')).toHaveTextContent('—');
  });

  it('submits create portfolio form and sends payload', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PortfolioDashboard />
      </MemoryRouter>
    );

    await screen.findByRole('heading', { name: 'Przegląd inwestycji' });

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

  it('collapses strategies by default and finds a child while preserving the global total', async () => {
    const user = userEvent.setup();
    mockedPortfolioApi.list.mockResolvedValueOnce({ portfolios: [{ ...listResponse.portfolios[0],
      name: 'Emerytura', account_type: 'IKE', asset_value: 1000,
      children: [{ ...listResponse.portfolios[0], id: 2, parent_portfolio_id: 1, name: 'Długoterminowe', asset_value: 400 }],
    }] } as never);
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    const expand = await screen.findByRole('button', { name: 'Rozwiń strategie: Emerytura' });
    expect(screen.queryByRole('link', { name: /Długoterminowe/ })).not.toBeInTheDocument();
    await user.click(expand);
    expect(screen.getByRole('link', { name: /Długoterminowe/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Zwiń strategie: Emerytura' }));
    await user.type(screen.getByRole('searchbox'), 'dlugoterminowe');
    expect(screen.getByRole('link', { name: /Długoterminowe/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Emerytura/ })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Podsumowanie aktywnych kont' })).toHaveTextContent(/1.*000,00 PLN/);
    const allocation = screen.getByRole('region', { name: 'Gdzie są Twoje pieniądze' });
    expect(allocation).toHaveTextContent('100,00%');
    expect(allocation).not.toHaveTextContent(/1.*400,00 PLN/);
  });

  it('filters empty and archived accounts without changing active totals', async () => {
    const user = userEvent.setup();
    const base = listResponse.portfolios[0];
    mockedPortfolioApi.list.mockResolvedValueOnce({ portfolios: [base,
      { ...base, id: 2, name: 'Puste obligacje', account_type: 'BONDS', portfolio_value: 0, total_result: 0 },
      { ...base, id: 3, name: 'Stare konto', is_archived: true, portfolio_value: 50000 },
    ] } as never);
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    await screen.findByRole('link', { name: /Puste obligacje/ });
    expect(screen.queryByRole('link', { name: /Stare konto/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: 'Ukryj puste' }));
    expect(screen.queryByRole('link', { name: /Puste obligacje/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: 'Pokaż archiwalne' }));
    expect(screen.getByRole('link', { name: /Stare konto/ })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Podsumowanie aktywnych kont' })).toHaveTextContent(/12.*345,67 PLN/);
    await user.type(screen.getByRole('searchbox'), 'nieistniejące');
    expect(screen.getByText('Brak kont pasujących do filtrów.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Wyczyść filtry' }));
    expect(screen.getByRole('link', { name: /Puste obligacje/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Stare konto/ })).not.toBeInTheDocument();
  });

  it('sorts by value or profit and always places missing valuations last', async () => {
    const user = userEvent.setup();
    const base = listResponse.portfolios[0];
    mockedPortfolioApi.list.mockResolvedValueOnce({ portfolios: [
      { ...base, id: 1, name: 'Mniejsze', portfolio_value: 100, total_result: 50 },
      { ...base, id: 2, name: 'Większe', portfolio_value: 200, total_result: -10 },
      { ...base, id: 3, name: 'Brak ceny', valuation_status: 'incomplete', portfolio_value: 10000, total_result: 5000 },
    ] } as never);
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    await screen.findByRole('link', { name: /Mniejsze/ });
    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('link').map(link => link.textContent)).toEqual([
      'WiększeRachunek inwestycyjny', 'MniejszeRachunek inwestycyjny', 'Brak cenyRachunek inwestycyjny',
    ]);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sortowanie portfeli' }), 'result');
    expect(within(table).getAllByRole('link')[0]).toHaveTextContent('Mniejsze');
    expect(within(table).getAllByRole('link')[2]).toHaveTextContent('Brak ceny');
    expect(screen.getByRole('region', { name: 'Gdzie są Twoje pieniądze' })).toHaveTextContent('Uzupełnij wycenę');
  });

  it('shows estimated withdrawal only when it differs from assets', async () => {
    mockedPortfolioApi.list.mockResolvedValueOnce({ portfolios: [listResponse.portfolios[0],
      { ...listResponse.portfolios[0], id: 2, name: 'PPK testowe', account_type: 'PPK', asset_value: 1800, withdrawable_value: 1500 },
    ] } as never);
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    await screen.findByRole('link', { name: /PPK testowe/ });
    expect(screen.getAllByText(/Wypłata ≈/)).toHaveLength(1);
    expect(screen.getByText(/Wypłata ≈/)).toHaveTextContent(/1.*500,00 PLN/);
  });

  it('distinguishes an exceeded contribution limit from an unpublished limit', async () => {
    mockedPortfolioApi.limits.mockResolvedValueOnce({ limits: { year: 2027,
      IKE: { deposited: 27000, limit: 26000, percentage: 103.85 },
      IKZE: { deposited: 100, limit: null, percentage: null },
    } } as never);
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    await screen.findByRole('heading', { name: 'Limity wpłat · 2027' });
    expect(screen.getByText('Przekroczenie').parentElement).toHaveTextContent(/1.*000,00 PLN/);
    expect(screen.getByRole('progressbar', { name: 'Wykorzystanie limitu IKE' })).toHaveAttribute('aria-valuenow', '100');
    expect(screen.getByText('Limit nieopublikowany')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Wykorzystanie limitu IKZE' })).not.toHaveAttribute('aria-valuenow');
  });

  it('does not turn absent valuation fields into a zero even if the server omitted its status', async () => {
    mockedPortfolioApi.list.mockResolvedValueOnce({ portfolios: [{ ...listResponse.portfolios[0],
      portfolio_value: undefined, total_result: undefined, net_contributions: 600,
    }] } as never);
    render(<MemoryRouter><PortfolioDashboard /></MemoryRouter>);
    expect(await screen.findByRole('status')).toHaveTextContent('Niepełna wycena');
    expect(screen.getByText('Wartość aktywów', { selector: 'dt' }).parentElement).toHaveTextContent('—');
    expect(screen.getByText('Wynik inwestowania', { selector: 'dt' }).parentElement).toHaveTextContent('—');
    expect(screen.getByText('Kapitał wpłacony netto', { selector: 'dt' }).parentElement).toHaveTextContent('600,00 PLN');
  });
});
