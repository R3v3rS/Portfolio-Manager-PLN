import { HttpError, type QueryParams } from './http';
import { createApiClient } from './apiConfig';

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

export interface BudgetActionResult {
  message: string;
  open_loans?: EnvelopeLoan[];
}

const budgetHttp = createApiClient('/budget');

const budgetPath = {
  summary: '/summary',
  transactions: '/transactions',
  analytics: '/analytics',
  income: '/income',
  allocate: '/allocate',
  expense: '/expense',
  accountTransfer: '/account-transfer',
  envelopes: '/envelopes',
  closeEnvelope: '/envelopes/close',
  transferToPortfolio: '/transfer-to-portfolio',
  withdrawFromPortfolio: '/withdraw-from-portfolio',
  borrow: '/borrow',
  repay: '/repay',
  categories: '/categories',
  cloneBudget: '/budget/clone',
  accounts: '/accounts',
  reset: '/reset',
} as const;

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

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const normalizeEnvelope = (value: unknown): Envelope => {
  const source = isRecord(value) ? value : {};

  return {
    id: toNumber(source.id),
    category_id: toNumber(source.category_id),
    name: toString(source.name),
    icon: toString(source.icon, '✉️'),
    target_amount: source.target_amount == null ? undefined : toNumber(source.target_amount),
    balance: toNumber(source.balance),
    total_spent: source.total_spent == null ? undefined : toNumber(source.total_spent),
    total_allocated: source.total_allocated == null ? undefined : toNumber(source.total_allocated),
    total_spent_lifetime: source.total_spent_lifetime == null ? undefined : toNumber(source.total_spent_lifetime),
    category_name: source.category_name == null ? undefined : toString(source.category_name),
    outstanding_loans: source.outstanding_loans == null ? undefined : toNumber(source.outstanding_loans),
    type: source.type === 'LONG_TERM' ? 'LONG_TERM' : source.type === 'MONTHLY' ? 'MONTHLY' : undefined,
    target_month: source.target_month == null ? undefined : toString(source.target_month),
    status: source.status === 'CLOSED' ? 'CLOSED' : source.status === 'ACTIVE' ? 'ACTIVE' : undefined,
  };
};

const normalizeEnvelopeLoan = (value: unknown): EnvelopeLoan => {
  const source = isRecord(value) ? value : {};

  return {
    id: toNumber(source.id),
    source_envelope: toString(source.source_envelope),
    amount: toNumber(source.amount),
    remaining: toNumber(source.remaining),
    due_date: source.due_date == null ? undefined : toString(source.due_date),
    reason: toString(source.reason),
  };
};

const normalizeBudgetAccount = (value: unknown): BudgetAccount => {
  const source = isRecord(value) ? value : {};

  return {
    id: toNumber(source.id),
    name: toString(source.name),
    balance: toNumber(source.balance),
    currency: toString(source.currency, 'PLN'),
    free_pool: source.free_pool == null ? undefined : toNumber(source.free_pool),
  };
};

const normalizeEnvelopeCategory = (value: unknown): EnvelopeCategory => {
  const source = isRecord(value) ? value : {};

  return {
    id: toNumber(source.id),
    name: toString(source.name),
    icon: toString(source.icon, '📁'),
  };
};

const normalizeFlowAnalysis = (value: unknown): FlowAnalysis | undefined => {
  if (!isRecord(value)) return undefined;

  return {
    income: toNumber(value.income),
    investment_transfers: toNumber(value.investment_transfers),
    savings_rate: toNumber(value.savings_rate),
  };
};

const normalizeEnvelopeCategories = (value: unknown): EnvelopeCategory[] =>
  Array.isArray(value) ? value.map(normalizeEnvelopeCategory) : [];

const normalizeBudgetSummary = (value: unknown): BudgetSummary => {
  const source = isRecord(value) ? value : {};

  return {
    account_balance: toNumber(source.account_balance),
    free_pool: toNumber(source.free_pool),
    total_allocated: toNumber(source.total_allocated),
    total_borrowed: toNumber(source.total_borrowed),
    envelopes: Array.isArray(source.envelopes) ? source.envelopes.map(normalizeEnvelope) : [],
    loans: Array.isArray(source.loans) ? source.loans.map(normalizeEnvelopeLoan) : [],
    accounts: Array.isArray(source.accounts) ? source.accounts.map(normalizeBudgetAccount) : [],
    flow_analysis: normalizeFlowAnalysis(source.flow_analysis),
  };
};

const normalizeActionResult = (value: unknown, fallbackMessage: string): BudgetActionResult => {
  const source = isRecord(value) ? value : {};

  return {
    message: typeof source.message === 'string' && source.message.trim() ? source.message : fallbackMessage,
    open_loans: Array.isArray(source.open_loans) ? source.open_loans.map(normalizeEnvelopeLoan) : undefined,
  };
};

const withBudgetErrorMessage = async <T>(action: string, request: () => Promise<T>): Promise<T> => {
  try {
    return await request();
  } catch (error) {
    const fallbackMessage = `Nie udało się wykonać operacji: ${action}.`;

    if (error instanceof HttpError) {
      throw new HttpError(error.message || fallbackMessage, error.status, error.data);
    }

    if (error instanceof Error) {
      throw new Error(error.message || fallbackMessage);
    }

    throw new Error(fallbackMessage);
  }
};

const budgetQuery = (params: QueryParams): QueryParams => params;

export const budgetApi = {
  getSummary: async (accountId?: number, month?: string): Promise<BudgetSummary> => {
    const response = await withBudgetErrorMessage('pobranie podsumowania budżetu', () =>
      budgetHttp.get<unknown>(budgetPath.summary, { params: budgetQuery({ account_id: accountId, month }) })
    );

    return normalizeBudgetSummary(response);
  },

  getTransactions: <T = unknown>(accountId: number, envelopeId?: number | null, categoryId?: number | null): Promise<T> =>
    withBudgetErrorMessage('pobranie transakcji budżetowych', () =>
      budgetHttp.get<T>(budgetPath.transactions, {
        params: budgetQuery({
          account_id: accountId,
          envelope_id: envelopeId ?? undefined,
          category_id: categoryId ?? undefined,
        }),
      })
    ),

  getAnalytics: <T = unknown>(accountId: number, year: number, month: number): Promise<T> =>
    withBudgetErrorMessage('pobranie analityki budżetu', () =>
      budgetHttp.get<T>(budgetPath.analytics, { params: budgetQuery({ account_id: accountId, year, month }) })
    ),

  addIncome: async (accountId: number, amount: number, description?: string, date?: string): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('dodanie wpływu', () =>
      budgetHttp.post<unknown>(budgetPath.income, { account_id: accountId, amount, description, date })
    );

    return normalizeActionResult(response, 'Dodano wpływ.');
  },

  allocate: async (envelopeId: number, amount: number, date?: string): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('alokacja środków do koperty', () =>
      budgetHttp.post<unknown>(budgetPath.allocate, { envelope_id: envelopeId, amount, date })
    );

    return normalizeActionResult(response, 'Środki zostały przydzielone.');
  },

  expense: async (
    envelopeId: number | null,
    accountId: number,
    amount: number,
    description?: string,
    date?: string,
  ): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('zapisanie wydatku', () =>
      budgetHttp.post<unknown>(budgetPath.expense, { envelope_id: envelopeId, account_id: accountId, amount, description, date })
    );

    return normalizeActionResult(response, 'Wydatek został zapisany.');
  },

  transferBetweenAccounts: async (
    fromAccountId: number,
    toAccountId: number,
    amount: number,
    description?: string,
    date?: string,
    targetEnvelopeId?: number | null,
    sourceEnvelopeId?: number | null,
  ): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('transfer między kontami budżetowymi', () =>
      budgetHttp.post<unknown>(budgetPath.accountTransfer, {
        from_account_id: fromAccountId,
        to_account_id: toAccountId,
        amount,
        description,
        date,
        target_envelope_id: targetEnvelopeId,
        source_envelope_id: sourceEnvelopeId,
      })
    );

    return normalizeActionResult(response, 'Transfer został zapisany.');
  },

  getEnvelopes: async (accountId?: number): Promise<Envelope[]> => {
    const response = await withBudgetErrorMessage('pobranie kopert budżetowych', () =>
      budgetHttp.get<unknown>(budgetPath.envelopes, { params: budgetQuery({ account_id: accountId }) })
    );

    return Array.isArray(response) ? response.map(normalizeEnvelope) : [];
  },

  transferToPortfolio: async (
    budgetAccountId: number,
    portfolioId: number,
    amount: number,
    envelopeId?: number | null,
    description?: string,
    date?: string,
  ): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('transfer środków do portfela', () =>
      budgetHttp.post<unknown>(budgetPath.transferToPortfolio, {
        budget_account_id: budgetAccountId,
        portfolio_id: portfolioId,
        amount,
        envelope_id: envelopeId,
        description,
        date,
      })
    );

    return normalizeActionResult(response, 'Środki zostały przelane do portfela.');
  },

  withdrawFromPortfolio: async (
    portfolioId: number,
    budgetAccountId: number,
    amount: number,
    description?: string,
    date?: string,
  ): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('wypłata środków z portfela', () =>
      budgetHttp.post<unknown>(budgetPath.withdrawFromPortfolio, {
        portfolio_id: portfolioId,
        budget_account_id: budgetAccountId,
        amount,
        description,
        date,
      })
    );

    return normalizeActionResult(response, 'Środki zostały wypłacone z portfela.');
  },

  borrow: async (sourceEnvelopeId: number, amount: number, reason: string, dueDate?: string): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('pożyczka z koperty', () =>
      budgetHttp.post<unknown>(budgetPath.borrow, { source_envelope_id: sourceEnvelopeId, amount, reason, due_date: dueDate })
    );

    return normalizeActionResult(response, 'Pożyczka została zapisana.');
  },

  repay: async (loanId: number, amount: number): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('spłata pożyczki z koperty', () =>
      budgetHttp.post<unknown>(budgetPath.repay, { loan_id: loanId, amount })
    );

    return normalizeActionResult(response, 'Pożyczka została spłacona.');
  },

  createCategory: async (name: string, icon?: string): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('utworzenie kategorii budżetowej', () =>
      budgetHttp.post<unknown>(budgetPath.categories, { name, icon })
    );

    return normalizeActionResult(response, 'Kategoria została utworzona.');
  },

  createEnvelope: async (
    categoryId: number,
    accountId: number,
    name: string,
    icon?: string,
    targetAmount?: number,
    type: 'MONTHLY' | 'LONG_TERM' = 'MONTHLY',
    targetMonth?: string,
  ): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('utworzenie koperty budżetowej', () =>
      budgetHttp.post<unknown>(budgetPath.envelopes, {
        category_id: categoryId,
        account_id: accountId,
        name,
        icon,
        target_amount: targetAmount,
        type,
        target_month: targetMonth,
      })
    );

    return normalizeActionResult(response, 'Koperta została utworzona.');
  },

  updateEnvelope: async (envelopeId: number, payload: { targetAmount?: number; name?: string }): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('aktualizacja koperty budżetowej', () =>
      budgetHttp.patch<unknown>(`${budgetPath.envelopes}/${envelopeId}`, {
        target_amount: payload.targetAmount,
        name: payload.name,
      })
    );

    return normalizeActionResult(response, 'Koperta została zaktualizowana.');
  },

  closeEnvelope: async (envelopeId: number): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('zamknięcie koperty budżetowej', () =>
      budgetHttp.post<unknown>(budgetPath.closeEnvelope, { envelope_id: envelopeId })
    );

    return normalizeActionResult(response, 'Koperta została zamknięta.');
  },

  cloneBudget: async (accountId: number, fromMonth: string, toMonth: string): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('klonowanie budżetu', () =>
      budgetHttp.post<unknown>(budgetPath.cloneBudget, { account_id: accountId, from_month: fromMonth, to_month: toMonth })
    );

    return normalizeActionResult(response, 'Budżet został sklonowany.');
  },

  createAccount: async (name: string, balance?: number, currency?: string): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('utworzenie konta budżetowego', () =>
      budgetHttp.post<unknown>(budgetPath.accounts, { name, balance, currency })
    );

    return normalizeActionResult(response, 'Konto budżetowe zostało utworzone.');
  },

  getCategories: async (): Promise<EnvelopeCategory[]> => {
    const response = await withBudgetErrorMessage('pobranie kategorii budżetowych', () =>
      budgetHttp.get<unknown>(budgetPath.categories)
    );

    return normalizeEnvelopeCategories(response);
  },

  reset: async (): Promise<BudgetActionResult> => {
    const response = await withBudgetErrorMessage('reset danych budżetu', () =>
      budgetHttp.post<unknown>(budgetPath.reset)
    );

    return normalizeActionResult(response, 'Dane budżetu zostały zresetowane.');
  },
};
