import type { LoanMutationDto } from './api-contract';
import { type QueryParams } from './http';
import { createApiClient } from './apiConfig';

export interface LoanPayload {
  exclude_from_net_worth?: boolean;
  name: string;
  original_amount: number;
  duration_months: number;
  start_date: string;
  installment_type: string;
  initial_rate: number;
  category?: string;
}

export interface LoanRatePayload {
  interest_rate: number;
  valid_from_date: string;
}

export interface LoanOverpaymentPayload {
  amount: number;
  date: string;
  type?: 'REDUCE_TERM' | 'REDUCE_INSTALLMENT';
  account_id?: number;
}

export interface LoanStatus {
  estimated_balance: number;
  next_installment: number;
  next_due_date: string | null;
  recorded_payments: number;
  confirmed_balance: number | null;
  confirmed_on: string | null;
}

export interface LoanSummary extends LoanStatus {
  exclude_from_net_worth?: boolean;
  id: number;
  name: string;
  original_amount: number;
  duration_months: number;
  start_date: string;
  installment_type: string;
  category?: string;
}

export interface LoanScheduleEntry {
  month: number;
  date: string;
  interest_rate: number;
  installment: number;
  principal_part: number;
  interest_part: number;
  overpayment: number;
  remaining_balance: number;
  overpayment_type: 'REDUCE_TERM' | 'REDUCE_INSTALLMENT' | null;
}

export interface LoanScheduleMetrics {
  total_interest: number;
}

export interface LoanScheduleComparisonMetrics {
  interest_saved: number;
  months_saved: number;
  interest_saved_to_date?: number;
  total_interest?: number;
}

export interface LoanScheduleOverpayment {
  id: number;
  amount: number;
  date: string;
  type?: 'REDUCE_TERM' | 'REDUCE_INSTALLMENT';
  budget_linked: boolean;
}

export interface LoanInstallmentPayment {
  id: number;
  installment_month: number;
  due_date: string;
  paid_on: string;
  amount: number;
  budget_linked: boolean;
}

export interface LoanRate { id: number; interest_rate: number; valid_from_date: string }
export interface LoanBalanceCheck { id: number; balance: number; checked_on: string }

export interface LoanScheduleResponse {
  loan: {
    exclude_from_net_worth?: boolean;
    id: number;
    name: string;
    category?: string;
    initial_rate: number;
    original_amount: number;
    duration_months: number;
    start_date: string;
    installment_type: string;
  };
  baseline: LoanScheduleMetrics & { schedule: LoanScheduleEntry[] };
  actual: LoanScheduleMetrics & { schedule: LoanScheduleEntry[] };
  simulation: LoanScheduleMetrics & { schedule: LoanScheduleEntry[] };
  actual_metrics: LoanScheduleComparisonMetrics;
  simulated_metrics: LoanScheduleComparisonMetrics;
  overpayments_list: LoanScheduleOverpayment[];
  payments_list: LoanInstallmentPayment[];
  rates_list: LoanRate[];
  balance_checks_list: LoanBalanceCheck[];
  status: LoanStatus;
}

export interface ScheduleQuery {
  sim_amount?: number;
  sim_date?: string;
  monthly_overpayment?: number;
  simulated_action?: 'REDUCE_TERM' | 'REDUCE_INSTALLMENT';
}

const loansHttp = createApiClient('/loans');

const loanPath = {
  list: '/',
  byId: (id: number) => `/${id}`,
  rates: (id: number) => `/${id}/rates`,
  overpayments: (id: number) => `/${id}/overpayments`,
  schedule: (id: number) => `/${id}/schedule`,
  payments: (id: number) => `/${id}/payments`,
  balanceChecks: (id: number) => `/${id}/balance-checks`,
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
  if (value == null) return fallback;
  return String(value);
};

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);

const normalizeStatus = (value: unknown): LoanStatus => {
  const source = isRecord(value) ? value : {};
  return {
    estimated_balance: toNumber(source.estimated_balance),
    next_installment: toNumber(source.next_installment),
    next_due_date: source.next_due_date == null ? null : toString(source.next_due_date),
    recorded_payments: toNumber(source.recorded_payments),
    confirmed_balance: source.confirmed_balance == null ? null : toNumber(source.confirmed_balance),
    confirmed_on: source.confirmed_on == null ? null : toString(source.confirmed_on),
  };
};

const normalizeLoanSummary = (value: unknown): LoanSummary => {
  const source = isRecord(value) ? value : {};

  return {
    id: toNumber(source.id),
    name: toString(source.name),
    original_amount: toNumber(source.original_amount),
    duration_months: toNumber(source.duration_months),
    start_date: toString(source.start_date),
    installment_type: toString(source.installment_type),
    category: source.category == null ? undefined : toString(source.category),
    exclude_from_net_worth: source.exclude_from_net_worth === true || source.exclude_from_net_worth === 1,
    ...normalizeStatus(source),
  };
};

const normalizeScheduleEntry = (value: unknown): LoanScheduleEntry => {
  const source = isRecord(value) ? value : {};

  return {
    month: toNumber(source.month),
    date: toString(source.date),
    interest_rate: toNumber(source.interest_rate),
    installment: toNumber(source.installment),
    principal_part: toNumber(source.principal_part),
    interest_part: toNumber(source.interest_part),
    overpayment: toNumber(source.overpayment),
    remaining_balance: toNumber(source.remaining_balance),
    overpayment_type:
      source.overpayment_type === 'REDUCE_INSTALLMENT'
        ? 'REDUCE_INSTALLMENT'
        : source.overpayment_type === 'REDUCE_TERM'
          ? 'REDUCE_TERM'
          : null,
  };
};

const normalizeMetrics = (value: unknown): LoanScheduleMetrics & LoanScheduleComparisonMetrics & { schedule?: LoanScheduleEntry[] } => {
  const source = isRecord(value) ? value : {};

  return {
    total_interest: toNumber(source.total_interest),
    interest_saved: toNumber(source.interest_saved),
    months_saved: toNumber(source.months_saved),
    interest_saved_to_date: source.interest_saved_to_date == null ? undefined : toNumber(source.interest_saved_to_date),
    schedule: Array.isArray(source.schedule) ? source.schedule.map(normalizeScheduleEntry) : undefined,
  };
};

const normalizeOverpayment = (value: unknown): LoanScheduleOverpayment => {
  const source = isRecord(value) ? value : {};

  return {
    id: toNumber(source.id),
    amount: toNumber(source.amount),
    date: toString(source.date),
    type:
      source.type === 'REDUCE_INSTALLMENT'
        ? 'REDUCE_INSTALLMENT'
        : source.type === 'REDUCE_TERM'
          ? 'REDUCE_TERM'
          : undefined,
    budget_linked: Boolean(source.budget_entry_id),
  };
};

const normalizeLoanSchedule = (value: unknown): LoanScheduleResponse => {
  const source = isRecord(value) ? value : {};
  const loan = isRecord(source.loan) ? source.loan : {};
  const baseline = normalizeMetrics(source.baseline);
  const actual = normalizeMetrics(source.actual);
  const simulation = normalizeMetrics(source.simulation);
  const actualMetrics = normalizeMetrics(source.actual_metrics);
  const simulatedMetrics = normalizeMetrics(source.simulated_metrics);

  return {
    loan: {
      id: toNumber(loan.id),
      name: toString(loan.name),
      category: loan.category == null ? undefined : toString(loan.category),
      exclude_from_net_worth: loan.exclude_from_net_worth === true || loan.exclude_from_net_worth === 1,
      initial_rate: toNumber(loan.initial_rate),
      original_amount: toNumber(loan.original_amount),
      duration_months: toNumber(loan.duration_months),
      start_date: toString(loan.start_date),
      installment_type: toString(loan.installment_type),
    },
    baseline: {
      total_interest: baseline.total_interest,
      schedule: baseline.schedule ?? [],
    },
    actual: {
      total_interest: actual.total_interest,
      schedule: actual.schedule ?? simulation.schedule ?? [],
    },
    simulation: {
      total_interest: simulation.total_interest,
      schedule: simulation.schedule ?? [],
    },
    actual_metrics: {
      total_interest: actualMetrics.total_interest,
      interest_saved: actualMetrics.interest_saved,
      months_saved: actualMetrics.months_saved,
      interest_saved_to_date: actualMetrics.interest_saved_to_date,
    },
    simulated_metrics: {
      total_interest: simulatedMetrics.total_interest,
      interest_saved: simulatedMetrics.interest_saved,
      months_saved: simulatedMetrics.months_saved,
      interest_saved_to_date: simulatedMetrics.interest_saved_to_date,
    },
    overpayments_list: Array.isArray(source.overpayments_list) ? source.overpayments_list.map(normalizeOverpayment) : [],
    payments_list: Array.isArray(source.payments_list) ? source.payments_list.map(value => {
      const item = isRecord(value) ? value : {};
      return {
        id: toNumber(item.id), installment_month: toNumber(item.installment_month),
        due_date: toString(item.due_date), paid_on: toString(item.paid_on),
        amount: toNumber(item.amount), budget_linked: Boolean(item.budget_linked),
      };
    }) : [],
    rates_list: Array.isArray(source.rates_list) ? source.rates_list.map(value => {
      const item = isRecord(value) ? value : {};
      return { id: toNumber(item.id), interest_rate: toNumber(item.interest_rate), valid_from_date: toString(item.valid_from_date) };
    }) : [],
    balance_checks_list: Array.isArray(source.balance_checks_list) ? source.balance_checks_list.map(value => {
      const item = isRecord(value) ? value : {};
      return { id: toNumber(item.id), balance: toNumber(item.balance), checked_on: toString(item.checked_on) };
    }) : [],
    status: normalizeStatus(source.status),
  };
};

const loanQuery = (params?: ScheduleQuery): QueryParams | undefined => (params ? { ...params } : undefined);

export const getLoans = async (): Promise<LoanSummary[]> => {
  const response = await loansHttp.get<unknown>(loanPath.list);
  return Array.isArray(response) ? response.map(normalizeLoanSummary) : [];
};

export const createLoan = (data: LoanPayload) => loansHttp.post<LoanMutationDto>(loanPath.list, data);
export const setLoanNetWorthExclusion = (id: number, excluded: boolean) =>
  loansHttp.put<{ id: number; exclude_from_net_worth: boolean }>(loanPath.byId(id) + '/net-worth-inclusion', { exclude_from_net_worth: excluded });
export const addRate = (id: number, data: LoanRatePayload) => loansHttp.post<LoanMutationDto>(loanPath.rates(id), data);
export const addOverpayment = (id: number, data: LoanOverpaymentPayload) => loansHttp.post<LoanMutationDto>(loanPath.overpayments(id), data);
export const deleteOverpayment = (id: number, overpaymentId: number) => loansHttp.delete(loanPath.overpayments(id) + '/' + overpaymentId);
export const recordInstallment = (id: number, data: { installment_month: number; paid_on: string; amount: number; account_id?: number }) =>
  loansHttp.post<{ id: number; budget_entry_id: number | null }>(loanPath.payments(id), data);
export const deleteInstallment = (id: number, paymentId: number) => loansHttp.delete(loanPath.payments(id) + '/' + paymentId);
export const recordBalanceCheck = (id: number, data: { balance: number; checked_on: string }) =>
  loansHttp.post<{ id: number }>(loanPath.balanceChecks(id), data);
export const deleteLoan = (id: number) => loansHttp.delete<LoanMutationDto>(loanPath.byId(id));
export const getSchedule = async (id: number, params?: ScheduleQuery): Promise<LoanScheduleResponse> => {
  const response = await loansHttp.get<unknown>(loanPath.schedule(id), { params: loanQuery(params) });
  return normalizeLoanSchedule(response);
};

export default loansHttp;
