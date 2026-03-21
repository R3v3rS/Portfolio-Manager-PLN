import { createHttpClient } from './http';

const api = createHttpClient('/api/symbol-map');

export type MappingCurrency = 'PLN' | 'USD' | 'EUR' | 'GBP';

export interface SymbolMapping {
  id: number;
  symbol_input: string;
  ticker: string;
  currency: MappingCurrency | null;
  created_at: string | null;
}

export interface CreateSymbolMappingPayload {
  symbol_input: string;
  ticker: string;
  currency: MappingCurrency;
}

export interface UpdateSymbolMappingPayload {
  ticker?: string;
  currency?: MappingCurrency;
}

export const symbolMapApi = {
  getAll: (): Promise<SymbolMapping[]> => api.get('/'),
  create: (payload: CreateSymbolMappingPayload): Promise<SymbolMapping> => api.post('/', payload),
  update: (id: number, payload: UpdateSymbolMappingPayload): Promise<SymbolMapping> => api.put(`/${id}`, payload),
  delete: async (id: number): Promise<void> => {
    await api.delete(`/${id}`);
  },
};
