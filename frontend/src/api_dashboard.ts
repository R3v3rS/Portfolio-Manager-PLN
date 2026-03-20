import { http } from './lib/http';

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

export const dashboardApi = {
  getGlobalSummary: () => http.get<GlobalSummary>('/api/dashboard/global-summary'),
};
