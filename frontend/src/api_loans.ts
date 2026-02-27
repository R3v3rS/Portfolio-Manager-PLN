import axios from 'axios';

const api = axios.create({
  baseURL: '/api/loans',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getLoans = () => api.get('/');
export const createLoan = (data: any) => api.post('/', data);
export const addRate = (id: number, data: any) => api.post(`/${id}/rates`, data);
export const addOverpayment = (id: number, data: any) => api.post(`/${id}/overpayments`, data);
export const deleteLoan = (id: number) => api.delete(`/${id}`);
export const getSchedule = (id: number, params?: any) => api.get(`/${id}/schedule`, { params });

export default api;
