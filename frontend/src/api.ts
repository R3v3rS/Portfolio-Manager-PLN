import { createHttpClient } from './http';
import type { Portfolio, Transaction } from './types';

const portfolioHttp = createHttpClient('/api/portfolio');

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

export interface PortfolioLimitsResponse {
  limits: TaxLimitsResponse;
}

export const portfolioApi = {
  list: () => portfolioHttp.get<PortfolioListResponse>('/list'),
  limits: () => portfolioHttp.get<PortfolioLimitsResponse>('/limits'),
  create: (payload: CreatePortfolioPayload) => portfolioHttp.post('/create', payload),
  remove: (portfolioId: number) => portfolioHttp.delete(`/${portfolioId}`),
  listTransactions: () => portfolioHttp.get<TransactionsListResponse>('/transactions/all'),
};

export default portfolioHttp;
