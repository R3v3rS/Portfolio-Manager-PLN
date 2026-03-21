import axios from 'axios';
import { extractErrorMessage, extractPayload } from './apiEnvelope';

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

export interface ScheduleQuery {
  sim_amount?: number;
  sim_date?: string;
  monthly_overpayment?: number;
  simulated_action?: 'REDUCE_TERM' | 'REDUCE_INSTALLMENT';
}

const api = axios.create({
  baseURL: '/api/loans',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => {
    response.data = extractPayload(response.data);
    return response;
  },
  (error) => {
    if (error?.response?.data) {
      const details =
        typeof error.response.data === 'object' && error.response.data?.error?.details !== undefined
          ? error.response.data.error.details
          : undefined;
      const message = extractErrorMessage(error.response.data, error.message);
      error.response.data = {
        ...error.response.data,
        error: message,
        details,
      };
      error.message = message;
    }
    return Promise.reject(error);
  }
);

export const getLoans = () => api.get('/');
export const createLoan = (data: LoanPayload) => api.post('/', data);
export const addRate = (id: number, data: LoanRatePayload) => api.post(`/${id}/rates`, data);
export const addOverpayment = (id: number, data: LoanOverpaymentPayload) => api.post(`/${id}/overpayments`, data);
export const deleteLoan = (id: number) => api.delete(`/${id}`);
export const getSchedule = (id: number, params?: ScheduleQuery) => api.get(`/${id}/schedule`, { params });

export default api;
