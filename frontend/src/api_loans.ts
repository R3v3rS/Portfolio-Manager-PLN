import { type QueryParams } from './http';
import { createApiClient } from './apiConfig';

export interface LoanPayload {
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
}

export interface LoanSummary {
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
  amount: number;
  date: string;
  type?: 'REDUCE_TERM' | 'REDUCE_INSTALLMENT';
}

export interface LoanScheduleResponse {
  loan: {
    id: number;
    name: string;
    category?: string;
    initial_rate: number;
  };
  baseline: LoanScheduleMetrics & { schedule: LoanScheduleEntry[] };
  simulation: LoanScheduleMetrics & { schedule: LoanScheduleEntry[] };
  actual_metrics: LoanScheduleComparisonMetrics;
  simulated_metrics: LoanScheduleComparisonMetrics;
  overpayments_list: LoanScheduleOverpayment[];
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
    amount: toNumber(source.amount),
    date: toString(source.date),
    type:
      source.type === 'REDUCE_INSTALLMENT'
        ? 'REDUCE_INSTALLMENT'
        : source.type === 'REDUCE_TERM'
          ? 'REDUCE_TERM'
          : undefined,
  };
};

const normalizeLoanSchedule = (value: unknown): LoanScheduleResponse => {
  const source = isRecord(value) ? value : {};
  const loan = isRecord(source.loan) ? source.loan : {};
  const baseline = normalizeMetrics(source.baseline);
  const simulation = normalizeMetrics(source.simulation);
  const actualMetrics = normalizeMetrics(source.actual_metrics);
  const simulatedMetrics = normalizeMetrics(source.simulated_metrics);

  return {
    loan: {
      id: toNumber(loan.id),
      name: toString(loan.name),
      category: loan.category == null ? undefined : toString(loan.category),
      initial_rate: toNumber(loan.initial_rate),
    },
    baseline: {
      total_interest: baseline.total_interest,
      schedule: baseline.schedule ?? [],
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
  };
};

const loanQuery = (params?: ScheduleQuery): QueryParams | undefined => (params ? { ...params } : undefined);

export const getLoans = async (): Promise<LoanSummary[]> => {
  const response = await loansHttp.get<unknown>(loanPath.list);
  return Array.isArray(response) ? response.map(normalizeLoanSummary) : [];
};

export const createLoan = (data: LoanPayload) => loansHttp.post<{ message: string; id: number }>(loanPath.list, data);
export const addRate = (id: number, data: LoanRatePayload) => loansHttp.post<{ message: string }>(loanPath.rates(id), data);
export const addOverpayment = (id: number, data: LoanOverpaymentPayload) => loansHttp.post<{ message: string }>(loanPath.overpayments(id), data);
export const deleteLoan = (id: number) => loansHttp.delete<{ message: string }>(loanPath.byId(id));
export const getSchedule = async (id: number, params?: ScheduleQuery): Promise<LoanScheduleResponse> => {
  const response = await loansHttp.get<unknown>(loanPath.schedule(id), { params: loanQuery(params) });
  return normalizeLoanSchedule(response);
};

export default loansHttp;
