import { HttpError, type QueryParams } from './http';
import type { ApiErrorEnvelope, XtbImportErrorDetailsDto, XtbImportSuccessDto } from './api-contract';
import { createApiClient } from './apiConfig';
import type { Bond, ClosedPosition, ClosedPositionCycle, EquityAllocation, Holding, Portfolio, PortfolioValue, Transaction } from './types';
import type { PPKSummary, PPKTransaction } from './services/ppkCalculator';

const portfolioHttp = createApiClient('/portfolio');

export interface TaxLimitData {
  deposited: number;
  limit: number;
  percentage: number;
}

export interface TaxLimitsResponse {
  year: number;
  IKE: TaxLimitData;
  IKZE: TaxLimitData;
}

export interface CreatePortfolioPayload {
  name: string;
  initial_cash: number;
  account_type: 'STANDARD' | 'IKE' | 'BONDS' | 'SAVINGS' | 'PPK';
  created_at: string;
}

export interface PortfolioListResponse {
  portfolios: Portfolio[];
}

export interface TransactionsListResponse {
  transactions: Transaction[];
}

export interface MonthlyDividendPoint {
  label: string;
  amount: number;
}

export interface PortfolioHistoryPoint {
  date: string;
  label: string;
  value: number;
  net_contributions?: number;
  benchmark_value?: number;
  benchmark_inflation?: number;
  cash_value?: number;
  holdings_value?: number;
}

export interface PriceHistoryPoint {
  date: string;
  close_price: number;
}

export interface PriceHistoryResponse {
  history: PriceHistoryPoint[];
  last_updated: string | null;
}

export interface PortfolioAuditDifference {
  type: 'quantity_mismatch' | 'total_cost_mismatch' | 'cash_mismatch';
  ticker?: string;
  expected: number;
  actual: number;
}

export interface PortfolioAuditResult {
  is_consistent: boolean;
  differences: PortfolioAuditDifference[];
  rebuilt_state: {
    cash: number;
    realized_profit_total: number;
    holdings: Record<string, { quantity: number; total_cost: number; avg_price: number }>;
  } | null;
}

export interface PPKPerformanceResponse {
  start_week: string | null;
  start_price: number;
  current_price: number;
  return_pln: number;
  return_pct: number;
  chart: { 
    week: string; 
    price: number; 
    value?: number; 
    net_value?: number;
    net_contributions?: number;
  }[];
}

export interface PPKTransactionsResponse {
  transactions: PPKTransaction[];
  summary: PPKSummary | null;
  currentPrice: { price: number; date: string } | null;
}

export interface XtbImportResult {
  ok: boolean;
  message: string | null;
  missingSymbols: string[];
}

export interface PortfolioLimitsResponse {
  limits: TaxLimitsResponse;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
};

const toString = (value: unknown, fallback = ''): string => {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return fallback;
  return String(value);
};

const toOptionalString = (value: unknown): string | null => {
  if (typeof value === 'string') return value;
  return null;
};

const toStringArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.map((entry) => toString(entry)).filter(Boolean) : [];

const normalizePortfolio = (value: unknown): Portfolio => {
  const source = isRecord(value) ? (value as Partial<XtbImportSuccessDto> & Record<string, unknown>) : {};
  const accountType = source.account_type;

  return {
    id: toNumber(source.id),
    name: toString(source.name),
    account_type:
      accountType === 'IKE' || accountType === 'BONDS' || accountType === 'SAVINGS' || accountType === 'PPK'
        ? accountType
        : 'STANDARD',
    current_cash: toNumber(source.current_cash),
    total_deposits: toNumber(source.total_deposits),
    savings_rate: toNumber(source.savings_rate),
    last_interest_date: typeof source.last_interest_date === 'string' ? source.last_interest_date : undefined,
    created_at: typeof source.created_at === 'string' ? source.created_at : undefined,
    portfolio_value: source.portfolio_value == null ? undefined : toNumber(source.portfolio_value),
    cash_value: source.cash_value == null ? undefined : toNumber(source.cash_value),
    holdings_value: source.holdings_value == null ? undefined : toNumber(source.holdings_value),
    total_dividends: source.total_dividends == null ? undefined : toNumber(source.total_dividends),
    open_positions_result: source.open_positions_result == null ? undefined : toNumber(source.open_positions_result),
    total_result: source.total_result == null ? undefined : toNumber(source.total_result),
    total_result_percent: source.total_result_percent == null ? undefined : toNumber(source.total_result_percent),
    is_empty: typeof source.is_empty === 'boolean' ? source.is_empty : undefined,
  };
};

const normalizePortfolioListResponse = (value: unknown): PortfolioListResponse => {
  const source = isRecord(value) ? value : {};

  return {
    portfolios: Array.isArray(source.portfolios) ? source.portfolios.map(normalizePortfolio) : [],
  };
};

const normalizeHolding = (value: unknown): Holding => {
  const source = isRecord(value) ? value : {};

  return {
    id: toNumber(source.id),
    portfolio_id: toNumber(source.portfolio_id),
    ticker: toString(source.ticker),
    quantity: toNumber(source.quantity),
    average_buy_price: toNumber(source.average_buy_price),
    total_cost: toNumber(source.total_cost),
    current_price: source.current_price == null ? undefined : toNumber(source.current_price),
    current_value: source.current_value == null ? undefined : toNumber(source.current_value),
    profit_loss: source.profit_loss == null ? undefined : toNumber(source.profit_loss),
    profit_loss_percent: source.profit_loss_percent == null ? undefined : toNumber(source.profit_loss_percent),
    weight_percent: source.weight_percent == null ? undefined : toNumber(source.weight_percent),
    company_name: typeof source.company_name === 'string' ? source.company_name : undefined,
    sector: typeof source.sector === 'string' ? source.sector : undefined,
    industry: typeof source.industry === 'string' ? source.industry : undefined,
    auto_fx_fees: typeof source.auto_fx_fees === 'boolean' ? source.auto_fx_fees : undefined,
    fx_rate_used: source.fx_rate_used == null ? undefined : toNumber(source.fx_rate_used),
    currency: typeof source.currency === 'string' ? source.currency : undefined,
    price_last_updated_at: source.price_last_updated_at == null ? null : toString(source.price_last_updated_at),
  };
};

const normalizeTransaction = (value: unknown): Transaction => {
  const source = isRecord(value) ? value : {};
  const type = source.type;

  return {
    id: toNumber(source.id),
    portfolio_id: toNumber(source.portfolio_id),
    ticker: toString(source.ticker, 'CASH'),
    date: toString(source.date),
    type:
      type === 'BUY' || type === 'SELL' || type === 'DEPOSIT' || type === 'WITHDRAW' || type === 'DIVIDEND' || type === 'INTEREST'
        ? type
        : 'BUY',
    quantity: toNumber(source.quantity),
    price: toNumber(source.price),
    total_value: toNumber(source.total_value),
    realized_profit: source.realized_profit == null ? undefined : toNumber(source.realized_profit),
    commission: source.commission == null ? undefined : toNumber(source.commission),
  };
};

const normalizePortfolioValue = (value: unknown): PortfolioValue & { live_interest?: number } => {
  const source = isRecord(value) ? value : {};

  return {
    portfolio_value: toNumber(source.portfolio_value),
    cash_value: toNumber(source.cash_value),
    holdings_value: toNumber(source.holdings_value),
    total_dividends: toNumber(source.total_dividends),
    total_interest: source.total_interest == null ? undefined : toNumber(source.total_interest),
    open_positions_result: toNumber(source.open_positions_result),
    total_result: toNumber(source.total_result),
    total_result_percent: toNumber(source.total_result_percent),
    xirr_percent: source.xirr_percent == null ? undefined : toNumber(source.xirr_percent),
    live_interest: source.live_interest == null ? undefined : toNumber(source.live_interest),
    change_1d: source.change_1d == null ? undefined : toNumber(source.change_1d),
    change_1d_percent: source.change_1d_percent == null ? undefined : toNumber(source.change_1d_percent),
    change_7d: source.change_7d == null ? undefined : toNumber(source.change_7d),
    change_7d_percent: source.change_7d_percent == null ? undefined : toNumber(source.change_7d_percent),
  };
};

const normalizeBond = (value: unknown): Bond => {
  const source = isRecord(value) ? value : {};

  return {
    id: toNumber(source.id),
    portfolio_id: toNumber(source.portfolio_id),
    name: toString(source.name),
    principal: toNumber(source.principal),
    interest_rate: toNumber(source.interest_rate),
    purchase_date: toString(source.purchase_date),
    accrued_interest: toNumber(source.accrued_interest),
    total_value: toNumber(source.total_value),
  };
};

const normalizeMonthlyDividendPoint = (value: unknown): MonthlyDividendPoint => {
  const source = isRecord(value) ? value : {};
  return { label: toString(source.label), amount: toNumber(source.amount) };
};

const normalizePortfolioHistoryPoint = (value: unknown): PortfolioHistoryPoint => {
  const source = isRecord(value) ? value : {};
  return {
    date: toString(source.date),
    label: toString(source.label),
    value: toNumber(source.value),
    net_contributions: source.net_contributions == null ? undefined : toNumber(source.net_contributions),
    benchmark_value: source.benchmark_value == null ? undefined : toNumber(source.benchmark_value),
    cash_value: source.cash_value == null ? undefined : toNumber(source.cash_value),
    holdings_value: source.holdings_value == null ? undefined : toNumber(source.holdings_value),
  };
};

const normalizePriceHistoryPoint = (value: unknown): PriceHistoryPoint => {
  const source = isRecord(value) ? value : {};
  return { date: toString(source.date), close_price: toNumber(source.close_price) };
};

const normalizeClosedPosition = (value: unknown): ClosedPosition => {
  const source = isRecord(value) ? value : {};
  return {
    ticker: toString(source.ticker),
    company_name: source.company_name == null ? null : toString(source.company_name),
    realized_profit: toNumber(source.realized_profit),
    invested_capital: toNumber(source.invested_capital),
    profit_percent_on_capital: source.profit_percent_on_capital == null ? null : toNumber(source.profit_percent_on_capital),
    last_sell_date: source.last_sell_date == null ? null : toString(source.last_sell_date),
  };
};

const normalizeClosedPositionCycle = (value: unknown): ClosedPositionCycle => {
  const source = isRecord(value) ? value : {};
  const status = source.status;
  return {
    ticker: toString(source.ticker),
    company_name: source.company_name == null ? null : toString(source.company_name),
    cycle_id: toNumber(source.cycle_id),
    opened_at: source.opened_at == null ? null : toString(source.opened_at),
    closed_at: source.closed_at == null ? null : toString(source.closed_at),
    realized_profit: toNumber(source.realized_profit),
    invested_capital: toNumber(source.invested_capital),
    average_invested_capital: source.average_invested_capital == null ? null : toNumber(source.average_invested_capital),
    holding_period_days: source.holding_period_days == null ? null : toNumber(source.holding_period_days),
    profit_percent_on_capital: source.profit_percent_on_capital == null ? null : toNumber(source.profit_percent_on_capital),
    annualized_return_percent: source.annualized_return_percent == null ? null : toNumber(source.annualized_return_percent),
    buy_count: source.buy_count == null ? undefined : toNumber(source.buy_count),
    sell_count: source.sell_count == null ? undefined : toNumber(source.sell_count),
    status: status === 'CLOSED' || status === 'PARTIALLY_CLOSED' ? status : undefined,
    is_partially_closed: typeof source.is_partially_closed === 'boolean' ? source.is_partially_closed : undefined,
    remaining_quantity: source.remaining_quantity == null ? undefined : toNumber(source.remaining_quantity),
  };
};

const normalizeAuditResult = (value: unknown): PortfolioAuditResult => {
  const source = isRecord(value) ? value : {};
  const rebuiltState = isRecord(source.rebuilt_state) ? source.rebuilt_state : null;
  return {
    is_consistent: Boolean(source.is_consistent),
    differences: Array.isArray(source.differences)
      ? source.differences.map((entry) => {
          const diff = isRecord(entry) ? entry : {};
          const type = diff.type;
          return {
            type: type === 'total_cost_mismatch' || type === 'cash_mismatch' ? type : 'quantity_mismatch',
            ticker: typeof diff.ticker === 'string' ? diff.ticker : undefined,
            expected: toNumber(diff.expected),
            actual: toNumber(diff.actual),
          };
        })
      : [],
    rebuilt_state: rebuiltState
      ? {
          cash: toNumber(rebuiltState.cash),
          realized_profit_total: toNumber(rebuiltState.realized_profit_total),
          holdings: isRecord(rebuiltState.holdings)
            ? Object.fromEntries(
                Object.entries(rebuiltState.holdings).map(([ticker, holding]) => {
                  const rawHolding = isRecord(holding) ? holding : {};
                  return [
                    ticker,
                    {
                      quantity: toNumber(rawHolding.quantity),
                      total_cost: toNumber(rawHolding.total_cost),
                      avg_price: toNumber(rawHolding.avg_price),
                    },
                  ];
                })
              )
            : {},
        }
      : null,
  };
};

const normalizePpkTransaction = (value: unknown): PPKTransaction => {
  const source = isRecord(value) ? value : {};
  return {
    id: toNumber(source.id),
    portfolio_id: toNumber(source.portfolio_id),
    date: toString(source.date),
    employee_units: toNumber(source.employee_units),
    employer_units: toNumber(source.employer_units),
    price_per_unit: toNumber(source.price_per_unit),
  };
};

const normalizeEquityAllocation = (value: unknown): EquityAllocation => {
  const source = isRecord(value) ? value : {};
  return {
    ticker: toString(source.ticker),
    name: toString(source.name),
    value: toNumber(source.value),
    percentage: toNumber(source.percentage),
  };
};

const normalizePpkSummary = (value: unknown): PPKSummary | null => {
  if (!isRecord(value)) return null;
  return {
    totalUnits: toNumber(value.totalUnits),
    averagePrice: toNumber(value.averagePrice),
    totalContribution: toNumber(value.totalContribution),
    currentValue: toNumber(value.currentValue),
    profit: toNumber(value.profit),
    tax: toNumber(value.tax),
    netProfit: toNumber(value.netProfit),
    totalPurchaseValue: toNumber(value.totalPurchaseValue),
    totalCurrentValue: toNumber(value.totalCurrentValue),
    totalNetValue: toNumber(value.totalNetValue),
    totalTax: toNumber(value.totalTax),
    totalProfit: toNumber(value.totalProfit),
  };
};

export const normalizeXtbImportResult = (value: unknown): XtbImportResult => {
  const source = isRecord(value) ? (value as Partial<XtbImportSuccessDto> & Record<string, unknown>) : {};

  return {
    ok: true,
    message: toOptionalString(source.message),
    missingSymbols: toStringArray(source.missing_symbols),
  };
};

export const normalizeXtbImportError = (error: unknown): XtbImportResult => {
  if (error instanceof HttpError) {
    const errorEnvelope = isRecord(error.data) && isRecord(error.data.error)
      ? (error.data as unknown as ApiErrorEnvelope<XtbImportErrorDetailsDto>)
      : undefined;

    return {
      ok: false,
      message: errorEnvelope?.error.message ?? error.message ?? 'Import failed.',
      missingSymbols: toStringArray(errorEnvelope?.error.details?.missing_symbols),
    };
  }

  if (error instanceof Error) {
    return { ok: false, message: error.message, missingSymbols: [] };
  }

  return { ok: false, message: 'Unknown error', missingSymbols: [] };
};

export const portfolioApi = {
  list: async (): Promise<PortfolioListResponse> => {
    const response = await portfolioHttp.get<unknown>('/list');
    return normalizePortfolioListResponse(response);
  },
  limits: () => portfolioHttp.get<PortfolioLimitsResponse>('/limits'),
  create: (payload: CreatePortfolioPayload) => portfolioHttp.post('/create', payload),
  remove: (portfolioId: number) => portfolioHttp.delete(`/${portfolioId}`),
  listTransactions: (ticker?: string) => portfolioHttp.get<TransactionsListResponse>('/transactions/all', { params: ticker ? { ticker } : undefined }),
  listNormalized: async (): Promise<Portfolio[]> => {
    return (await portfolioApi.list()).portfolios;
  },
  getHoldings: async (portfolioId: number, params?: QueryParams): Promise<Holding[]> => {
    const response = await portfolioHttp.get<unknown>(`/holdings/${portfolioId}`, { params });
    const holdings = isRecord(response) ? response.holdings : undefined;
    return Array.isArray(holdings) ? holdings.map(normalizeHolding) : [];
  },
  getEquityAllocation: async (portfolioId: number): Promise<EquityAllocation[]> => {
    const response = await portfolioHttp.get<unknown>(`/allocation/${portfolioId}`);
    const allocation = isRecord(response) ? response.allocation : undefined;
    return Array.isArray(allocation) ? allocation.map(normalizeEquityAllocation) : [];
  },
  getValue: async (portfolioId: number): Promise<PortfolioValue & { live_interest?: number }> => {
    const response = await portfolioHttp.get<unknown>(`/value/${portfolioId}`);
    return normalizePortfolioValue(response);
  },
  getTransactions: async (portfolioId: number): Promise<Transaction[]> => {
    const response = await portfolioHttp.get<unknown>(`/transactions/${portfolioId}`);
    const transactions = isRecord(response) ? response.transactions : undefined;
    return Array.isArray(transactions) ? transactions.map(normalizeTransaction) : [];
  },
  getMonthlyDividends: async (portfolioId: number): Promise<MonthlyDividendPoint[]> => {
    const response = await portfolioHttp.get<unknown>(`/dividends/monthly/${portfolioId}`);
    const monthlyDividends = isRecord(response) ? response.monthly_dividends : undefined;
    return Array.isArray(monthlyDividends) ? monthlyDividends.map(normalizeMonthlyDividendPoint) : [];
  },
  getMonthlyHistory: async (portfolioId: number, benchmark?: string): Promise<PortfolioHistoryPoint[]> => {
    const response = await portfolioHttp.get<unknown>(`/history/monthly/${portfolioId}`, {
      params: benchmark ? { benchmark } : undefined,
    });
    const history = isRecord(response) ? response.history : undefined;
    return Array.isArray(history) ? history.map(normalizePortfolioHistoryPoint) : [];
  },
  getProfitHistory: async (portfolioId: number, days?: number): Promise<PortfolioHistoryPoint[]> => {
    const response = await portfolioHttp.get<unknown>(`/history/profit/${portfolioId}`, {
      params: days ? { days } : undefined,
    });
    const history = isRecord(response) ? response.history : undefined;
    return Array.isArray(history) ? history.map(normalizePortfolioHistoryPoint) : [];
  },
  getValueHistory: async (portfolioId: number, days?: number): Promise<PortfolioHistoryPoint[]> => {
    const response = await portfolioHttp.get<unknown>(`/history/value/${portfolioId}`, {
      params: days ? { days } : undefined,
    });
    const history = isRecord(response) ? response.history : undefined;
    return Array.isArray(history) ? history.map(normalizePortfolioHistoryPoint) : [];
  },
  getPriceHistory: async (ticker: string): Promise<PriceHistoryResponse> => {
    const response = await portfolioHttp.get<unknown>(`/history/${ticker}`);
    const source = isRecord(response) ? response : {};
    return {
      history: Array.isArray(source.history) ? source.history.map(normalizePriceHistoryPoint) : [],
      last_updated: toOptionalString(source.last_updated),
    };
  },
  getBonds: async (portfolioId: number): Promise<Bond[]> => {
    const response = await portfolioHttp.get<unknown>(`/bonds/${portfolioId}`);
    const bonds = isRecord(response) ? response.bonds : undefined;
    return Array.isArray(bonds) ? bonds.map(normalizeBond) : [];
  },
  getClosedPositions: async (portfolioId: number): Promise<{ positions: ClosedPosition[]; total_historical_profit: number }> => {
    const response = await portfolioHttp.get<unknown>(`/${portfolioId}/closed-positions`);
    const source = isRecord(response) ? response : {};
    return {
      positions: Array.isArray(source.positions) ? source.positions.map(normalizeClosedPosition) : [],
      total_historical_profit: toNumber(source.total_historical_profit),
    };
  },
  getClosedPositionCycles: async (portfolioId: number): Promise<{ positions: ClosedPositionCycle[]; total_historical_profit: number }> => {
    const response = await portfolioHttp.get<unknown>(`/${portfolioId}/closed-position-cycles`);
    const source = isRecord(response) ? response : {};
    return {
      positions: Array.isArray(source.positions) ? source.positions.map(normalizeClosedPositionCycle) : [],
      total_historical_profit: toNumber(source.total_historical_profit),
    };
  },
  runAudit: async (portfolioId: number): Promise<PortfolioAuditResult> => {
    const response = await portfolioHttp.get<unknown>(`/${portfolioId}/audit`);
    return normalizeAuditResult(response);
  },
  rebuild: async (portfolioId: number): Promise<{ message: string | null }> => {
    const response = await portfolioHttp.post<unknown>(`/${portfolioId}/rebuild`);
    const source = isRecord(response) ? response : {};
    return { message: toOptionalString(source.message) };
  },
  clear: async (portfolioId: number): Promise<{ message: string | null }> => {
    const response = await portfolioHttp.post<unknown>(`/${portfolioId}/clear`);
    const source = isRecord(response) ? response : {};
    return { message: toOptionalString(source.message) };
  },
  importXtbCsv: async (portfolio_id: number, file: File): Promise<XtbImportResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await portfolioHttp.post<unknown>(`/${portfolio_id}/import/xtb`, formData);
    return normalizeXtbImportResult(response);
  },
  buy: (payload: {
    portfolio_id: number;
    ticker: string;
    quantity: number;
    price: number;
    date: string;
    commission?: number;
    auto_fx_fees?: boolean;
  }) => portfolioHttp.post('/buy', payload),
  sell: (payload: { portfolio_id: number; ticker: string; quantity: number; price: number; date?: string }) =>
    portfolioHttp.post('/sell', payload),
  addDividend: (payload: { portfolio_id: number; ticker: string; amount: number; date: string }) =>
    portfolioHttp.post('/dividend', payload),
  addBond: (payload: {
    portfolio_id: number;
    name: string;
    principal: number;
    interest_rate: number;
    purchase_date: string;
  }) => portfolioHttp.post('/bonds', payload),
  updateSavingsRate: (payload: { portfolio_id: number; rate: number }) =>
    portfolioHttp.post('/savings/rate', payload),
  addSavingsInterest: (payload: { portfolio_id: number; amount: number; date: string }) =>
    portfolioHttp.post('/savings/interest/manual', payload),
  addPpkTransaction: (payload: {
    portfolio_id: number;
    date: string;
    employeeUnits: number;
    employerUnits: number;
    pricePerUnit: number;
  }) => portfolioHttp.post('/ppk/transactions', payload),
  getPpkPerformance: async (portfolioId: number): Promise<PPKPerformanceResponse> => {
    const response = await portfolioHttp.get<unknown>(`/ppk/performance/${portfolioId}`);
    const source = isRecord(response) ? response : {};
    return {
      start_week: toOptionalString(source.start_week),
      start_price: toNumber(source.start_price),
      current_price: toNumber(source.current_price),
      return_pln: toNumber(source.return_pln),
      return_pct: toNumber(source.return_pct),
      chart: Array.isArray(source.chart)
        ? source.chart.map((point) => {
            const p = isRecord(point) ? point : {};
            return { 
              week: toString(p.week), 
              price: toNumber(p.price),
              value: p.value !== undefined ? toNumber(p.value) : undefined,
              net_value: p.net_value !== undefined ? toNumber(p.net_value) : undefined,
              net_contributions: p.net_contributions !== undefined ? toNumber(p.net_contributions) : undefined
            };
          })
        : [],
    };
  },
  getPpkTransactions: async (portfolioId: number): Promise<PPKTransactionsResponse> => {
    const response = await portfolioHttp.get<unknown>(`/ppk/transactions/${portfolioId}`);
    const source = isRecord(response) ? response : {};
    const currentPrice = isRecord(source.currentPrice)
      ? {
          price: toNumber(source.currentPrice.price),
          date: toString(source.currentPrice.date),
        }
      : null;

    return {
      transactions: Array.isArray(source.transactions) ? source.transactions.map(normalizePpkTransaction) : [],
      summary: normalizePpkSummary(source.summary),
      currentPrice,
    };
  },
};

export default portfolioHttp;
