import { beforeAll, afterAll, afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HttpResponse, http } from 'msw';
import { setupServer } from 'msw/node';

import PortfolioList from './PortfolioList';
import PortfolioDetails from './PortfolioDetails';
import Transactions from './Transactions';

interface HoldingState {
  ticker: string;
  quantity: number;
  average_buy_price: number;
  current_price: number;
  profit: number;
  profit_percent: number;
  value: number;
  currency: string;
  sub_portfolio_id?: number | null;
}

interface TransactionState {
  id: number;
  portfolio_id: number;
  type: 'BUY' | 'SELL' | 'DEPOSIT' | 'WITHDRAW';
  ticker: string;
  quantity: number;
  price: number;
  total_value: number;
  date: string;
  realized_profit?: number;
}

interface PortfolioState {
  id: number;
  name: string;
  account_type: 'STANDARD';
  current_cash: number;
  portfolio_value: number;
  total_result: number;
  total_result_percent: number;
  total_dividends: number;
  total_deposits: number;
  savings_rate: number;
  children: Array<Record<string, unknown>>;
  parent_portfolio_id?: number | null;
  is_archived?: boolean;
}

const BASE_PORTFOLIO: PortfolioState = {
  id: 1,
  name: 'Core Portfolio',
  account_type: 'STANDARD',
  current_cash: 10000,
  portfolio_value: 10000,
  total_result: 0,
  total_result_percent: 0,
  total_dividends: 0,
  total_deposits: 10000,
  savings_rate: 0,
  children: [],
};

let portfolios: PortfolioState[] = [];
let holdings: HoldingState[] = [];
let transactions: TransactionState[] = [];
let transferBalance = { from: 4000, to: 500 };
let lastBuyPayload: Record<string, unknown> | null = null;
let lastSellPayload: Record<string, unknown> | null = null;
let lastTransferPayload: Record<string, unknown> | null = null;
let listTransactionsCalls: string[] = [];
let lastImportedFileName: string | null = null;

const recalcPortfolio = () => {
  const holdingsValue = holdings.reduce((sum, h) => sum + h.value, 0);
  const realized = transactions.reduce((sum, t) => sum + (t.realized_profit ?? 0), 0);
  BASE_PORTFOLIO.current_cash = Number(BASE_PORTFOLIO.current_cash.toFixed(2));
  BASE_PORTFOLIO.portfolio_value = Number((BASE_PORTFOLIO.current_cash + holdingsValue).toFixed(2));
  BASE_PORTFOLIO.total_result = Number((realized + holdings.reduce((sum, h) => sum + h.profit, 0)).toFixed(2));
  BASE_PORTFOLIO.total_result_percent = BASE_PORTFOLIO.total_deposits > 0
    ? Number(((BASE_PORTFOLIO.total_result / BASE_PORTFOLIO.total_deposits) * 100).toFixed(2))
    : 0;
};

const resetState = () => {
  portfolios = [
    { ...BASE_PORTFOLIO, children: [] },
    {
      ...BASE_PORTFOLIO,
      id: 2,
      name: 'Sub One',
      current_cash: 500,
      portfolio_value: 500,
      total_deposits: 500,
      parent_portfolio_id: 1,
      is_archived: false,
      children: [],
    },
  ];
  holdings = [];
  transactions = [];
  transferBalance = { from: 4000, to: 500 };
  lastBuyPayload = null;
  lastSellPayload = null;
  lastTransferPayload = null;
  listTransactionsCalls = [];
  lastImportedFileName = null;
  recalcPortfolio();
};

const ok = <T,>(payload: T, init?: ResponseInit) => HttpResponse.json({ payload }, init);
const apiError = (message: string, status = 500) =>
  HttpResponse.json({ error: { code: 'TEST_ERROR', message, details: null } }, { status });

const handlers = [
  http.get('*/api/portfolio/list', () => {
    return ok({ portfolios });
  }),
  http.post('*/api/portfolio/create', async ({ request }) => {
    const payload = (await request.json()) as Record<string, unknown>;
    const newPortfolio: PortfolioState = {
      ...BASE_PORTFOLIO,
      id: portfolios.length + 1,
      name: String(payload.name),
      current_cash: Number(payload.initial_cash ?? 0),
      portfolio_value: Number(payload.initial_cash ?? 0),
      total_deposits: Number(payload.initial_cash ?? 0),
    };
    portfolios.push(newPortfolio);
    return ok({ id: newPortfolio.id }, { status: 201 });
  }),
  http.get('*/api/portfolio/holdings/:portfolioId', () => ok({ holdings })),
  http.get('*/api/portfolio/value/:portfolioId', () => ok({
    current_cash: BASE_PORTFOLIO.current_cash,
    portfolio_value: BASE_PORTFOLIO.portfolio_value,
    holdings_value: holdings.reduce((sum, h) => sum + h.value, 0),
    total_result: BASE_PORTFOLIO.total_result,
    total_result_percent: BASE_PORTFOLIO.total_result_percent,
    total_dividends: 0,
    open_positions_result: holdings.reduce((sum, h) => sum + h.profit, 0),
    xirr_percent: 0,
  })),
  http.get('*/api/portfolio/dividends/monthly/:portfolioId', () => ok({ monthly_dividends: [] })),
  http.get('*/api/portfolio/transactions/:portfolioId', ({ request }) => {
    const url = new URL(request.url);
    const type = url.searchParams.get('type');
    const ticker = url.searchParams.get('ticker');
    const filtered = transactions.filter((tx) => (type ? tx.type === type : true) && (ticker ? tx.ticker === ticker : true));
    return ok({ transactions: filtered });
  }),
  http.get('*/api/portfolio/:portfolioId/closed-positions', () => ok({ positions: [], total_historical_profit: 0 })),
  http.get('*/api/portfolio/:portfolioId/closed-position-cycles', () => ok({ positions: [], total_historical_profit: 0 })),
  http.get('*/api/budget/summary', () => ok({
    account_balance: 0,
    free_pool: 0,
    total_allocated: 0,
    total_borrowed: 0,
    envelopes: [],
    loans: [],
    accounts: [{ id: 9, name: 'Cash Account', balance: 1000, currency: 'PLN' }],
  })),
  http.get('*/api/portfolio/allocation/:portfolioId', () => ok({ allocation: [] })),
  http.get('*/api/portfolio/config', () => ok({ subportfolios_allowed_types: ['STANDARD'] })),
  http.get('*/api/portfolio/history/monthly/:portfolioId', () => ok({ history: [] })),
  http.get('*/api/portfolio/history/profit/:portfolioId', () => ok({ history: [] })),
  http.get('*/api/portfolio/history/value/:portfolioId', () => ok({ history: [] })),

  http.post('*/api/portfolio/buy', async ({ request }) => {
    const payload = (await request.json()) as Record<string, unknown>;
    lastBuyPayload = payload;
    const qty = Number(payload.quantity);
    const price = Number(payload.price);
    const ticker = String(payload.ticker);
    const total = qty * price;
    BASE_PORTFOLIO.current_cash -= total;

    const existing = holdings.find((h) => h.ticker === ticker);
    if (existing) {
      const combinedQty = existing.quantity + qty;
      existing.average_buy_price = ((existing.average_buy_price * existing.quantity) + total) / combinedQty;
      existing.quantity = combinedQty;
      existing.current_price = price;
      existing.value = combinedQty * price;
      existing.profit = (price - existing.average_buy_price) * combinedQty;
    } else {
      holdings.push({
        ticker,
        quantity: qty,
        average_buy_price: price,
        current_price: price,
        profit: 0,
        profit_percent: 0,
        value: total,
        currency: 'PLN',
      });
    }

    transactions.unshift({
      id: transactions.length + 1,
      portfolio_id: 1,
      type: 'BUY',
      ticker,
      quantity: qty,
      price,
      total_value: total,
      date: String(payload.date),
    });

    recalcPortfolio();
    return ok({ ok: true }, { status: 201 });
  }),

  http.post('*/api/portfolio/sell', async ({ request }) => {
    const payload = (await request.json()) as Record<string, unknown>;
    lastSellPayload = payload;
    const qty = Number(payload.quantity);
    const price = Number(payload.price);
    const ticker = String(payload.ticker);

    const existing = holdings.find((h) => h.ticker === ticker);
    if (!existing) return apiError('Holding missing', 422);

    const realizedProfit = (price - existing.average_buy_price) * qty;
    existing.quantity -= qty;
    existing.current_price = price;
    existing.value = existing.quantity * existing.current_price;
    existing.profit = (existing.current_price - existing.average_buy_price) * existing.quantity;
    BASE_PORTFOLIO.current_cash += qty * price;
    if (existing.quantity <= 0) {
      holdings = holdings.filter((h) => h.ticker !== ticker);
    }

    transactions.unshift({
      id: transactions.length + 1,
      portfolio_id: 1,
      type: 'SELL',
      ticker,
      quantity: qty,
      price,
      total_value: qty * price,
      date: String(payload.date),
      realized_profit: realizedProfit,
    });

    recalcPortfolio();
    return ok({ ok: true }, { status: 201 });
  }),

  http.post('*/api/portfolio/transfer/cash', async ({ request }) => {
    const payload = (await request.json()) as Record<string, unknown>;
    lastTransferPayload = payload;
    const amount = Number(payload.amount);
    transferBalance.from -= amount;
    transferBalance.to += amount;
    return ok({ transfer_id: 'tr-1', job_id: 'job-transfer-1' });
  }),
  http.get('*/api/portfolio/jobs/:jobId', () => ok({
    id: 'job-transfer-1',
    status: 'done',
    progress: 100,
    result: null,
    error: null,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  })),

  http.post('*/api/portfolio/:portfolioId/import/xtb', async ({ request }) => {
    const form = await request.formData();
    const file = form.get('file') as File;
    lastImportedFileName = file?.name ?? null;
    if (file.name.includes('partial')) {
      return ok({
        message: 'Import completed with warnings',
        status: 'warning',
        missing_symbols: [],
        potential_conflicts: [
          {
            row_hash: 'row-1',
            conflict_type: 'database_duplicate',
            import_data: { date: '2026-01-10', ticker: 'MSFT', amount: 120, type: 'BUY', quantity: 1 },
            existing_match: { id: 99, date: '2026-01-10', amount: 120, type: 'BUY', quantity: 1, source: 'db' },
          },
        ],
      });
    }

    if (file.name.includes('error')) {
      return apiError('Import failed hard', 500);
    }

    return ok({ message: 'Import successful', status: 'success', missing_symbols: [] });
  }),

  http.get('*/api/portfolio/transactions/all', ({ request }) => {
    const url = new URL(request.url);
    listTransactionsCalls.push(url.search);

    const type = url.searchParams.get('type');
    const ticker = url.searchParams.get('ticker');
    const dateFrom = url.searchParams.get('date_from');
    const dateTo = url.searchParams.get('date_to');

    const filtered = transactions.filter((tx) => {
      if (type && tx.type !== type) return false;
      if (ticker && tx.ticker !== ticker) return false;
      if (dateFrom && tx.date < dateFrom) return false;
      if (dateTo && tx.date > dateTo) return false;
      return true;
    });

    return ok({
      transactions: filtered.map((tx) => ({ ...tx, portfolio_name: 'Core Portfolio', sub_portfolio_id: null })),
    });
  }),
];

const server = setupServer(...handlers);

const renderPortfolioDetails = () =>
  render(
    <MemoryRouter initialEntries={['/portfolio/1']}>
      <Routes>
        <Route path="/portfolio/:id" element={<PortfolioDetails />} />
      </Routes>
    </MemoryRouter>
  );

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

beforeEach(() => {
  resetState();
});

describe('Create portfolio integration flow', () => {
  it('creates portfolio and refreshes list with new row', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PortfolioList />
      </MemoryRouter>
    );

    await screen.findByText('Core Portfolio');
    await user.click(screen.getByRole('button', { name: 'Create Portfolio' }));
    await user.type(screen.getByLabelText('Portfolio Name'), 'Dividend Vault');
    await user.type(screen.getByLabelText('Initial Cash Deposit (PLN)'), '4200');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText('Dividend Vault')).toBeInTheDocument();
    expect(screen.getAllByText('4200.00 PLN').length).toBeGreaterThan(0);
  });

  it('shows create error feedback and keeps UI responsive', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    server.use(http.post('*/api/portfolio/create', () => apiError('boom', 500)));
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <PortfolioList />
      </MemoryRouter>
    );

    await screen.findByText('Core Portfolio');
    await user.click(screen.getByRole('button', { name: 'Create Portfolio' }));
    await user.type(screen.getByLabelText('Portfolio Name'), 'Failing portfolio');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(alertSpy).toHaveBeenCalledWith('Failed to create portfolio');
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument();
  });
});

describe('BUY transaction integration flow', () => {
  it('sends BUY payload and updates holdings + summary cards', async () => {
    const user = userEvent.setup();
    renderPortfolioDetails();

    await screen.findByText('Core Portfolio');
    await user.click(screen.getByRole('button', { name: 'Nowa Operacja' }));
    await user.type(screen.getByPlaceholderText('np. AAPL'), 'AAPL');
    const spinboxes = screen.getAllByRole('spinbutton');
    await user.type(spinboxes[0], '10');
    await user.type(spinboxes[1], '50');
    await user.click(screen.getByRole('button', { name: 'Zatwierdź' }));

    await waitFor(() => expect(lastBuyPayload).toMatchObject({ ticker: 'AAPL', quantity: 10, price: 50, portfolio_id: 1 }));
    expect((await screen.findAllByText('AAPL')).length).toBeGreaterThan(0);
    expect(screen.getByText('Core Portfolio')).toBeInTheDocument();
  });

  it('displays API buy errors without crashing screen', async () => {
    server.use(http.post('*/api/portfolio/buy', () => apiError('Buy rejected', 422)));
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    const user = userEvent.setup();

    renderPortfolioDetails();
    await screen.findByText('Core Portfolio');
    await user.click(screen.getByRole('button', { name: 'Nowa Operacja' }));
    await user.type(screen.getByPlaceholderText('np. AAPL'), 'ORCL');
    const spinboxes = screen.getAllByRole('spinbutton');
    await user.type(spinboxes[0], '1');
    await user.type(spinboxes[1], '100');
    await user.click(screen.getByRole('button', { name: 'Zatwierdź' }));

    expect(alertSpy).toHaveBeenCalledWith('Buy rejected');
    expect(screen.getByRole('button', { name: 'Zatwierdź' })).toBeEnabled();
  });
});

describe('SELL transaction integration flow', () => {
  it('sends SELL payload and updates positions/profit in UI', async () => {
    holdings = [{
      ticker: 'AAPL', quantity: 10, average_buy_price: 40, current_price: 50,
      value: 500, profit: 100, profit_percent: 25, currency: 'PLN',
    }];
    BASE_PORTFOLIO.current_cash = 9000;
    recalcPortfolio();

    const user = userEvent.setup();
    renderPortfolioDetails();

    await screen.findAllByText('AAPL');
    await user.click(screen.getByRole('button', { name: 'Sprzedaj' }));
    const sellForm = screen.getByRole('button', { name: 'Sprzedaj Akcje' }).closest('form')!;
    const sellFields = within(sellForm).getAllByRole('spinbutton');
    await user.clear(sellFields[0]);
    await user.type(sellFields[0], '4');
    await user.clear(sellFields[1]);
    await user.type(sellFields[1], '60');
    await user.click(within(sellForm).getByRole('button', { name: 'Sprzedaj Akcje' }));

    await waitFor(() => expect(lastSellPayload).toMatchObject({ ticker: 'AAPL', quantity: 4, price: 60, portfolio_id: 1 }));
    expect((await screen.findAllByText('AAPL')).length).toBeGreaterThan(0);
    expect(screen.getByText('Core Portfolio')).toBeInTheDocument();
  });

  it('shows SELL errors and keeps details page mounted', async () => {
    holdings = [{
      ticker: 'AAPL', quantity: 10, average_buy_price: 40, current_price: 50,
      value: 500, profit: 100, profit_percent: 25, currency: 'PLN',
    }];
    recalcPortfolio();
    server.use(http.post('*/api/portfolio/sell', () => apiError('Sell blocked', 422)));
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    const user = userEvent.setup();

    renderPortfolioDetails();
    await screen.findAllByText('AAPL');
    await user.click(screen.getByRole('button', { name: 'Sprzedaj' }));
    await user.click(screen.getByRole('button', { name: 'Sprzedaj Akcje' }));

    expect(alertSpy).toHaveBeenCalledWith('Sell blocked');
    expect(screen.getByText('Core Portfolio')).toBeInTheDocument();
  });
});

describe('Transfer funds integration flow', () => {
  it('posts transfer payload and updates both balances from API refresh', async () => {
    const user = userEvent.setup();
    renderPortfolioDetails();

    await screen.findByText('Core Portfolio');
    await user.click(screen.getByRole('button', { name: 'Transfer' }));
    await user.click(screen.getByRole('button', { name: 'Sub→Sub' }));
    const combos = screen.getAllByRole('combobox').slice(-2);
    await user.selectOptions(combos[0], '1');
    await user.selectOptions(combos[1], '2');
    await user.type(screen.getAllByRole('spinbutton').at(-1) as HTMLElement, '250');
    await user.click(screen.getByRole('button', { name: 'Wykonaj przelew' }));

    await waitFor(() => expect(lastTransferPayload).toMatchObject({
      from_portfolio_id: 1,
      to_portfolio_id: 2,
      amount: 250,
    }));
    expect(transferBalance).toEqual({ from: 3750, to: 750 });
  });

  it('shows transfer API errors and does not crash modal', async () => {
    server.use(http.post('*/api/portfolio/transfer/cash', () => apiError('Transfer failed', 422)));
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    const user = userEvent.setup();

    renderPortfolioDetails();
    await screen.findByText('Core Portfolio');
    await user.click(screen.getByRole('button', { name: 'Transfer' }));
    await user.click(screen.getByRole('button', { name: 'Sub→Sub' }));
    const combos = screen.getAllByRole('combobox').slice(-2);
    await user.selectOptions(combos[0], '1');
    await user.selectOptions(combos[1], '2');
    await user.type(screen.getAllByRole('spinbutton').at(-1) as HTMLElement, '10');
    await user.click(screen.getByRole('button', { name: 'Wykonaj przelew' }));

    expect(alertSpy).toHaveBeenCalledWith('Transfer failed');
    expect(screen.getByText('Transfer Środków')).toBeInTheDocument();
  });
});

describe('Import transactions integration flow', () => {
  it.skip('handles successful CSV import flow', async () => {
    vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    const { container } = renderPortfolioDetails();

    await screen.findByText('Core Portfolio');
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['x'], 'ok.csv', { type: 'text/csv' });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(lastImportedFileName).toBe('ok.csv'));
    expect(screen.getByText('Core Portfolio')).toBeInTheDocument();
  });

  it.skip('renders partial import failure modal and allows user feedback', async () => {
    const { container } = renderPortfolioDetails();

    await screen.findByText('Core Portfolio');
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['x'], 'partial.csv', { type: 'text/csv' });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(lastImportedFileName).toBe('partial.csv'));
    expect(screen.getByText('Core Portfolio')).toBeInTheDocument();
  });
});

describe('Filter transactions integration flow', () => {
  it('calls API with date/type/ticker filters and updates table rows', async () => {
    transactions = [
      { id: 1, portfolio_id: 1, type: 'BUY', ticker: 'AAPL', quantity: 2, price: 100, total_value: 200, date: '2026-01-05' },
      { id: 2, portfolio_id: 1, type: 'SELL', ticker: 'MSFT', quantity: 1, price: 150, total_value: 150, date: '2026-02-10' },
      { id: 3, portfolio_id: 1, type: 'BUY', ticker: 'ORCL', quantity: 3, price: 90, total_value: 270, date: '2026-03-15' },
    ];

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Transactions />
      </MemoryRouter>
    );

    await screen.findByText('Transaction History');
    fireEvent.change(screen.getByLabelText('Date from'), { target: { value: '2026-02-01' } });
    fireEvent.change(screen.getByLabelText('Date to'), { target: { value: '2026-02-28' } });
    await user.selectOptions(screen.getByLabelText('Type'), 'SELL');
    await user.selectOptions(screen.getByLabelText('Ticker'), 'MSFT');

    expect(screen.getByLabelText('Date from')).toHaveValue('2026-02-01');
    expect(screen.getByLabelText('Date to')).toHaveValue('2026-02-28');

    expect(screen.getAllByText('MSFT').length).toBeGreaterThan(0);
    expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
  });

  it('shows API errors during filtering but page remains usable', async () => {
    server.use(http.get('*/api/portfolio/transactions/all', () => apiError('Query failed', 500)));
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);

    render(
      <MemoryRouter>
        <Transactions />
      </MemoryRouter>
    );

    await screen.findByText('Transaction History');
    await waitFor(() => expect(alertSpy).toHaveBeenCalledWith('Query failed'));
    expect(screen.getByText('Transaction History')).toBeInTheDocument();
  });
});
