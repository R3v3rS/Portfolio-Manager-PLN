import { createApiClient } from './apiConfig';

export interface GlobalSummary {
  net_worth: number;
  total_assets: number;
  total_liabilities: number;
  liabilities_breakdown: {
    short_term: number;
    long_term: number;
  };
  assets_breakdown: {
    budget_cash: number;
    invest_cash: number;
    savings: number;
    bonds: number;
    stocks: number;
    ppk: number;
  };
  quick_stats: {
    free_pool: number;
    next_loan_installment: number;
    next_loan_date: string | null;
  };
}

export interface CurrentMonthDividends {
  received_this_month: number;
  expected_this_month: number;
  month_label: string;
  top_payers: Array<{
    ticker: string;
    amount: number;
    date: string;
  }>;
}

const dashboardHttp = createApiClient('/dashboard');

const EMPTY_GLOBAL_SUMMARY: GlobalSummary = {
  net_worth: 0,
  total_assets: 0,
  total_liabilities: 0,
  liabilities_breakdown: {
    short_term: 0,
    long_term: 0,
  },
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
};

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

const toNullableString = (value: unknown): string | null => {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  return normalized || null;
};

const toString = (value: unknown, fallback = ''): string => {
  if (typeof value !== 'string') return fallback;
  return value.trim();
};

const normalizeGlobalSummary = (value: unknown): GlobalSummary => {
  const source = isRecord(value) ? value : {};
  const liabilities = isRecord(source.liabilities_breakdown) ? source.liabilities_breakdown : {};
  const assets = isRecord(source.assets_breakdown) ? source.assets_breakdown : {};
  const quickStats = isRecord(source.quick_stats) ? source.quick_stats : {};

  return {
    net_worth: toNumber(source.net_worth),
    total_assets: toNumber(source.total_assets),
    total_liabilities: toNumber(source.total_liabilities),
    liabilities_breakdown: {
      short_term: toNumber(liabilities.short_term),
      long_term: toNumber(liabilities.long_term),
    },
    assets_breakdown: {
      budget_cash: toNumber(assets.budget_cash),
      invest_cash: toNumber(assets.invest_cash),
      savings: toNumber(assets.savings),
      bonds: toNumber(assets.bonds),
      stocks: toNumber(assets.stocks),
      ppk: toNumber(assets.ppk),
    },
    quick_stats: {
      free_pool: toNumber(quickStats.free_pool),
      next_loan_installment: toNumber(quickStats.next_loan_installment),
      next_loan_date: toNullableString(quickStats.next_loan_date),
    },
  };
};

const normalizeCurrentMonthDividends = (value: unknown): CurrentMonthDividends => {
  const source = isRecord(value) ? value : {};
  const topPayers = Array.isArray(source.top_payers) ? source.top_payers : [];

  return {
    received_this_month: toNumber(source.received_this_month),
    expected_this_month: toNumber(source.expected_this_month),
    month_label: toString(source.month_label),
    top_payers: topPayers
      .filter(isRecord)
      .map((payer) => ({
        ticker: toString(payer.ticker),
        amount: toNumber(payer.amount),
        date: toString(payer.date),
      }))
      .filter((payer) => payer.ticker.length > 0),
  };
};

export const dashboardApi = {
  getGlobalSummary: async (): Promise<GlobalSummary> => {
    const response = await dashboardHttp.get<unknown>('/global-summary');
    return normalizeGlobalSummary(response ?? EMPTY_GLOBAL_SUMMARY);
  },
  getCurrentMonthDividends: async (): Promise<CurrentMonthDividends> => {
    const response = await dashboardHttp.get<unknown>('/dividends/current-month');
    return normalizeCurrentMonthDividends(response ?? {});
  },
};

export { EMPTY_GLOBAL_SUMMARY };
