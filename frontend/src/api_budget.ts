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

const API_URL = 'http://localhost:5000/api/budget';

export const budgetApi = {
  getSummary: async (accountId?: number, month?: string): Promise<BudgetSummary> => {
    let url = accountId ? `${API_URL}/summary?account_id=${accountId}` : `${API_URL}/summary?`;
    if (month) url += `&month=${month}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch summary');
    return res.json();
  },

  getTransactions: async (accountId: number, envelopeId?: number | null, categoryId?: number | null) => {
    let url = `${API_URL}/transactions?account_id=${accountId}`;
    if (envelopeId) url += `&envelope_id=${envelopeId}`;
    if (categoryId) url += `&category_id=${categoryId}`;
    
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch transactions');
    return res.json();
  },

  getAnalytics: async (accountId: number, year: number, month: number) => {
    const res = await fetch(`${API_URL}/analytics?account_id=${accountId}&year=${year}&month=${month}`);
    if (!res.ok) throw new Error('Failed to fetch analytics');
    return res.json();
  },

  addIncome: async (accountId: number, amount: number, description?: string, date?: string) => {
    const res = await fetch(`${API_URL}/income`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_id: accountId, amount, description, date }),
    });
    if (!res.ok) throw new Error('Failed to add income');
    return res.json();
  },

  allocate: async (envelopeId: number, amount: number, date?: string) => {
    const res = await fetch(`${API_URL}/allocate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ envelope_id: envelopeId, amount, date }),
    });
    if (!res.ok) throw new Error('Failed to allocate');
    return res.json();
  },

  expense: async (envelopeId: number | null, accountId: number, amount: number, description?: string, date?: string) => {
    const res = await fetch(`${API_URL}/expense`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ envelope_id: envelopeId, account_id: accountId, amount, description, date }),
    });
    if (!res.ok) throw new Error('Failed to record expense');
    return res.json();
  },

  transferBetweenAccounts: async (fromAccountId: number, toAccountId: number, amount: number, description?: string, date?: string, targetEnvelopeId?: number | null, sourceEnvelopeId?: number | null) => {
    const res = await fetch(`${API_URL}/account-transfer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_account_id: fromAccountId, to_account_id: toAccountId, amount, description, date, target_envelope_id: targetEnvelopeId, source_envelope_id: sourceEnvelopeId }),
    });
    if (!res.ok) throw new Error('Failed to transfer between accounts');
    return res.json();
  },

  getEnvelopes: async (accountId?: number) => {
    const url = accountId ? `${API_URL}/envelopes?account_id=${accountId}` : `${API_URL}/envelopes`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch envelopes');
    return res.json();
  },

  transferToPortfolio: async (budgetAccountId: number, portfolioId: number, amount: number, envelopeId?: number | null, description?: string, date?: string) => {
    const res = await fetch(`${API_URL}/transfer-to-portfolio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ budget_account_id: budgetAccountId, portfolio_id: portfolioId, amount, envelope_id: envelopeId, description, date }),
    });
    if (!res.ok) throw new Error('Failed to transfer to investment portfolio');
    return res.json();
  },

  withdrawFromPortfolio: async (portfolioId: number, budgetAccountId: number, amount: number, description?: string, date?: string) => {
    const res = await fetch(`${API_URL}/withdraw-from-portfolio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ portfolio_id: portfolioId, budget_account_id: budgetAccountId, amount, description, date }),
    });
    if (!res.ok) throw new Error('Failed to withdraw from investment portfolio');
    return res.json();
  },

  borrow: async (sourceEnvelopeId: number, amount: number, reason: string, dueDate?: string) => {
    const res = await fetch(`${API_URL}/borrow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_envelope_id: sourceEnvelopeId, amount, reason, due_date: dueDate }),
    });
    if (!res.ok) throw new Error('Failed to borrow');
    return res.json();
  },

  repay: async (loanId: number, amount: number) => {
    const res = await fetch(`${API_URL}/repay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ loan_id: loanId, amount }),
    });
    if (!res.ok) throw new Error('Failed to repay loan');
    return res.json();
  },

  createCategory: async (name: string, icon?: string) => {
    const res = await fetch(`${API_URL}/categories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, icon }),
    });
    if (!res.ok) throw new Error('Failed to create category');
    return res.json();
  },

  createEnvelope: async (categoryId: number, accountId: number, name: string, icon?: string, targetAmount?: number, type: 'MONTHLY' | 'LONG_TERM' = 'MONTHLY', targetMonth?: string) => {
    const res = await fetch(`${API_URL}/envelopes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category_id: categoryId, account_id: accountId, name, icon, target_amount: targetAmount, type, target_month: targetMonth }),
    });
    if (!res.ok) throw new Error('Failed to create envelope');
    return res.json();
  },

  updateEnvelope: async (envelopeId: number, targetAmount: number) => {
    const res = await fetch(`${API_URL}/envelopes/${envelopeId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_amount: targetAmount }),
    });
    if (!res.ok) throw new Error('Failed to update envelope');
    return res.json();
  },

  closeEnvelope: async (envelopeId: number) => {
    const res = await fetch(`${API_URL}/envelopes/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ envelope_id: envelopeId }),
    });
    if (!res.ok) throw new Error('Failed to close envelope');
    return res.json();
  },

  cloneBudget: async (accountId: number, fromMonth: string, toMonth: string) => {
    const res = await fetch(`${API_URL}/budget/clone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_id: accountId, from_month: fromMonth, to_month: toMonth }),
    });
    if (!res.ok) throw new Error('Failed to clone budget');
    return res.json();
  },

  createAccount: async (name: string, balance?: number, currency?: string) => {
    const res = await fetch(`${API_URL}/accounts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, balance, currency }),
    });
    if (!res.ok) throw new Error('Failed to create account');
    return res.json();
  },
};
