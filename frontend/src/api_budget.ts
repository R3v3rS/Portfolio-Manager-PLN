import { parseJsonApiResponse } from './apiEnvelope';

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

export interface BudgetTransaction {
  id: number;
  type: string;
  amount: number;
  description: string;
  date: string;
  envelope_name?: string;
  envelope_icon?: string;
  category_name?: string;
  category_icon?: string;
}

export interface BudgetAnalytics {
  total_expenses: number;
  by_category: { name: string; value: number; fill: string }[];
  by_envelope: { name: string; value: number }[];
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
const API_URL = `${API_BASE_URL}/api/budget`;

const buildUrl = (path: string, params?: Record<string, string | number | undefined>) => {
  const url = new URL(`${API_URL}${path}`, window.location.origin);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  return `${url.pathname}${url.search}`;
};

export const budgetApi = {
  getSummary: async (accountId?: number, month?: string): Promise<BudgetSummary> => {
    const res = await fetch(buildUrl('/summary', { account_id: accountId, month }));
    return parseJsonApiResponse<BudgetSummary>(res, 'Failed to fetch summary');
  },

  getTransactions: async (accountId: number, envelopeId?: number | null, categoryId?: number | null): Promise<BudgetTransaction[]> => {
    const res = await fetch(buildUrl('/transactions', {
      account_id: accountId,
      envelope_id: envelopeId ?? undefined,
      category_id: categoryId ?? undefined,
    }));
    return parseJsonApiResponse<BudgetTransaction[]>(res, 'Failed to fetch transactions');
  },

  getAnalytics: async (accountId: number, year: number, month: number): Promise<BudgetAnalytics> => {
    const res = await fetch(buildUrl('/analytics', { account_id: accountId, year, month }));
    return parseJsonApiResponse<BudgetAnalytics>(res, 'Failed to fetch analytics');
  },

  addIncome: async (accountId: number, amount: number, description?: string, date?: string) => {
    const res = await fetch(`${API_URL}/income`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_id: accountId, amount, description, date }),
    });
    return parseJsonApiResponse(res, 'Failed to add income');
  },

  allocate: async (envelopeId: number, amount: number, date?: string) => {
    const res = await fetch(`${API_URL}/allocate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ envelope_id: envelopeId, amount, date }),
    });
    return parseJsonApiResponse(res, 'Failed to allocate');
  },

  expense: async (envelopeId: number | null, accountId: number, amount: number, description?: string, date?: string) => {
    const res = await fetch(`${API_URL}/expense`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ envelope_id: envelopeId, account_id: accountId, amount, description, date }),
    });
    return parseJsonApiResponse(res, 'Failed to record expense');
  },

  transferBetweenAccounts: async (fromAccountId: number, toAccountId: number, amount: number, description?: string, date?: string, targetEnvelopeId?: number | null, sourceEnvelopeId?: number | null) => {
    const res = await fetch(`${API_URL}/account-transfer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_account_id: fromAccountId, to_account_id: toAccountId, amount, description, date, target_envelope_id: targetEnvelopeId, source_envelope_id: sourceEnvelopeId }),
    });
    return parseJsonApiResponse(res, 'Failed to transfer between accounts');
  },

  getEnvelopes: async (accountId?: number) => {
    const url = accountId ? `${API_URL}/envelopes?account_id=${accountId}` : `${API_URL}/envelopes`;
    const res = await fetch(url);
    return parseJsonApiResponse(res, 'Failed to fetch envelopes');
  },

  transferToPortfolio: async (budgetAccountId: number, portfolioId: number, amount: number, envelopeId?: number | null, description?: string, date?: string) => {
    const res = await fetch(`${API_URL}/transfer-to-portfolio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ budget_account_id: budgetAccountId, portfolio_id: portfolioId, amount, envelope_id: envelopeId, description, date }),
    });
    return parseJsonApiResponse(res, 'Failed to transfer to investment portfolio');
  },

  withdrawFromPortfolio: async (portfolioId: number, budgetAccountId: number, amount: number, description?: string, date?: string) => {
    const res = await fetch(`${API_URL}/withdraw-from-portfolio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ portfolio_id: portfolioId, budget_account_id: budgetAccountId, amount, description, date }),
    });
    return parseJsonApiResponse(res, 'Failed to withdraw from investment portfolio');
  },

  borrow: async (sourceEnvelopeId: number, amount: number, reason: string, dueDate?: string) => {
    const res = await fetch(`${API_URL}/borrow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_envelope_id: sourceEnvelopeId, amount, reason, due_date: dueDate }),
    });
    return parseJsonApiResponse(res, 'Failed to borrow');
  },

  repay: async (loanId: number, amount: number) => {
    const res = await fetch(`${API_URL}/repay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loan_id: loanId, amount }),
    });
    return parseJsonApiResponse(res, 'Failed to repay loan');
  },

  createCategory: async (name: string, icon?: string) => {
    const res = await fetch(`${API_URL}/categories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, icon }),
    });
    return parseJsonApiResponse(res, 'Failed to create category');
  },

  createEnvelope: async (categoryId: number, accountId: number, name: string, icon?: string, targetAmount?: number, type: 'MONTHLY' | 'LONG_TERM' = 'MONTHLY', targetMonth?: string) => {
    const res = await fetch(`${API_URL}/envelopes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category_id: categoryId, account_id: accountId, name, icon, target_amount: targetAmount, type, target_month: targetMonth }),
    });
    return parseJsonApiResponse(res, 'Failed to create envelope');
  },

  updateEnvelope: async (
    envelopeId: number,
    payload: { targetAmount?: number; name?: string }
  ) => {
    const res = await fetch(`${API_URL}/envelopes/${envelopeId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_amount: payload.targetAmount,
        name: payload.name,
      }),
    });
    return parseJsonApiResponse(res, 'Failed to update envelope');
  },

  closeEnvelope: async (envelopeId: number) => {
    const res = await fetch(`${API_URL}/envelopes/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ envelope_id: envelopeId }),
    });
    return parseJsonApiResponse(res, 'Failed to close envelope');
  },

  cloneBudget: async (accountId: number, fromMonth: string, toMonth: string) => {
    const res = await fetch(`${API_URL}/budget/clone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_id: accountId, from_month: fromMonth, to_month: toMonth }),
    });
    return parseJsonApiResponse(res, 'Failed to clone budget');
  },

  createAccount: async (name: string, balance?: number, currency?: string) => {
    const res = await fetch(`${API_URL}/accounts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, balance, currency }),
    });
    return parseJsonApiResponse(res, 'Failed to create account');
  },
};
