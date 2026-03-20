import { http } from './lib/http';

const API_URL = '/api/symbol-map';

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
  getAll: (): Promise<SymbolMapping[]> => http.get(API_URL),
  create: (payload: CreateSymbolMappingPayload): Promise<SymbolMapping> => http.post(API_URL, payload),
  update: (id: number, payload: UpdateSymbolMappingPayload): Promise<SymbolMapping> => http.put(`${API_URL}/${id}`, payload),
  delete: async (id: number): Promise<void> => {
    await http.delete(`${API_URL}/${id}`);
  },
};
