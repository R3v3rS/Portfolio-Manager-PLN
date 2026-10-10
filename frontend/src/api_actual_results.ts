import { createApiClient } from './apiConfig';
export type ActualMonth = { date: string; opening_value: number | null; closing_value: number | null; net_deposits: number; profit: number | null; return_percent: number | null; partial_month: boolean; complete: boolean };
export type ActualResults = {
  valuation_basis?: string;
  from: string; to: string; currency: string; status: string; portfolio_names: string[];
  opening_value: number | null; closing_value: number | null; deposits: number; withdrawals: number; net_deposits: number;
  profit: number | null; dietz_percent: number | null; xirr_percent: number | null; dividends: number; interest: number;
  realized_profit: number; modeled_interest: number; recorded_commissions: number; transaction_count: number; internal_transfer_amount: number;
  reconciliation: { cash_difference: number | null; positions_mismatch: string[]; consistent: boolean | null };
  months: ActualMonth[]; positive_months: number; known_months: number; best_month: ActualMonth | null; worst_month: ActualMonth | null; warnings: string[];
};
const portfolio = createApiClient('/portfolio');
const goals = createApiClient('/investment-goals');
export const actualResultsApi = {
  portfolio: (id: number, from?: string,to?:string) => portfolio.get<ActualResults>(`/history/results/${id}`, { params: {...(from?{from}:{}),...(to?{to}:{})} }),
  goal: (id: number, from?: string) => goals.get<ActualResults>(`/${id}/results`, { params: from ? { from } : {} }),
};
