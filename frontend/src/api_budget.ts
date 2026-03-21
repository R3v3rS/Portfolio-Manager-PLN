import { createHttpClient } from './http';

export interface BudgetAccount {
  id: number;
  name: string;
  balance: number;
  currency: string;
  free_pool?: number;
}

export interface EnvelopeCategory {
  id: number;
  name: string;
  icon: string;
}

export interface Envelope {
  id: number;
  category_id: number;
  name: string;
  icon: string;
  target_amount?: number;
  balance: number;
  total_spent?: number;
  total_allocated?: number;
  total_spent_lifetime?: number;
  category_name?: string;
  outstanding_loans?: number;
  type?: 'MONTHLY' | 'LONG_TERM';
  target_month?: string;
  status?: 'ACTIVE' | 'CLOSED';
}

export interface EnvelopeLoan {
  id: number;
  source_envelope: string;
  amount: number;
  remaining: number;
  due_date?: string;
  reason: string;
}

export interface FlowAnalysis {
  income: number;
  investment_transfers: number;
  savings_rate: number;
}

export interface BudgetSummary {
  account_balance: number;
  free_pool: number;
  total_allocated: number;
  total_borrowed: number;
  envelopes: Envelope[];
  loans: EnvelopeLoan[];
  accounts: BudgetAccount[];
  flow_analysis?: FlowAnalysis;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const api = createHttpClient(`${API_BASE_URL}/api/budget`);

export const budgetApi = {
  getSummary: (accountId?: number, month?: string): Promise<BudgetSummary> =>
    api.get('/summary', { params: { account_id: accountId, month } }),

  getTransactions: <T = unknown>(accountId: number, envelopeId?: number | null, categoryId?: number | null): Promise<T> =>
    api.get<T>('/transactions', {
      params: {
        account_id: accountId,
        envelope_id: envelopeId ?? undefined,
        category_id: categoryId ?? undefined,
      },
    }),

  getAnalytics: <T = unknown>(accountId: number, year: number, month: number): Promise<T> =>
    api.get<T>('/analytics', { params: { account_id: accountId, year, month } }),

  addIncome: (accountId: number, amount: number, description?: string, date?: string) =>
    api.post('/income', { account_id: accountId, amount, description, date }),

  allocate: (envelopeId: number, amount: number, date?: string) =>
    api.post('/allocate', { envelope_id: envelopeId, amount, date }),

  expense: (envelopeId: number | null, accountId: number, amount: number, description?: string, date?: string) =>
    api.post('/expense', { envelope_id: envelopeId, account_id: accountId, amount, description, date }),

  transferBetweenAccounts: (
    fromAccountId: number,
    toAccountId: number,
    amount: number,
    description?: string,
    date?: string,
    targetEnvelopeId?: number | null,
    sourceEnvelopeId?: number | null,
  ) => api.post('/account-transfer', {
    from_account_id: fromAccountId,
    to_account_id: toAccountId,
    amount,
    description,
    date,
    target_envelope_id: targetEnvelopeId,
    source_envelope_id: sourceEnvelopeId,
  }),

  getEnvelopes: (accountId?: number) => api.get('/envelopes', { params: { account_id: accountId } }),

  transferToPortfolio: (
    budgetAccountId: number,
    portfolioId: number,
    amount: number,
    envelopeId?: number | null,
    description?: string,
    date?: string,
  ) => api.post('/transfer-to-portfolio', {
    budget_account_id: budgetAccountId,
    portfolio_id: portfolioId,
    amount,
    envelope_id: envelopeId,
    description,
    date,
  }),

  withdrawFromPortfolio: (
    portfolioId: number,
    budgetAccountId: number,
    amount: number,
    description?: string,
    date?: string,
  ) => api.post('/withdraw-from-portfolio', {
    portfolio_id: portfolioId,
    budget_account_id: budgetAccountId,
    amount,
    description,
    date,
  }),

  borrow: (sourceEnvelopeId: number, amount: number, reason: string, dueDate?: string) =>
    api.post('/borrow', { source_envelope_id: sourceEnvelopeId, amount, reason, due_date: dueDate }),

  repay: (loanId: number, amount: number) => api.post('/repay', { loan_id: loanId, amount }),

  createCategory: (name: string, icon?: string) => api.post('/categories', { name, icon }),

  createEnvelope: (
    categoryId: number,
    accountId: number,
    name: string,
    icon?: string,
    targetAmount?: number,
    type: 'MONTHLY' | 'LONG_TERM' = 'MONTHLY',
    targetMonth?: string,
  ) => api.post('/envelopes', {
    category_id: categoryId,
    account_id: accountId,
    name,
    icon,
    target_amount: targetAmount,
    type,
    target_month: targetMonth,
  }),

  updateEnvelope: (envelopeId: number, payload: { targetAmount?: number; name?: string }) =>
    api.patch(`/envelopes/${envelopeId}`, {
      target_amount: payload.targetAmount,
      name: payload.name,
    }),

  closeEnvelope: (envelopeId: number) => api.post('/envelopes/close', { envelope_id: envelopeId }),

  cloneBudget: (accountId: number, fromMonth: string, toMonth: string) =>
    api.post('/budget/clone', { account_id: accountId, from_month: fromMonth, to_month: toMonth }),

  createAccount: (name: string, balance?: number, currency?: string) =>
    api.post('/accounts', { name, balance, currency }),

  getCategories: () => api.get<EnvelopeCategory[]>('/categories'),
  reset: () => api.post('/reset'),
};
