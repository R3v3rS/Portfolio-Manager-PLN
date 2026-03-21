import { parseJsonApiResponse } from './apiEnvelope';

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
  async getAll(): Promise<SymbolMapping[]> {
    const response = await fetch(API_URL);
    return parseJsonApiResponse<SymbolMapping[]>(response);
  },

  async create(payload: CreateSymbolMappingPayload): Promise<SymbolMapping> {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return parseJsonApiResponse<SymbolMapping>(response);
  },

  async update(id: number, payload: UpdateSymbolMappingPayload): Promise<SymbolMapping> {
    const response = await fetch(`${API_URL}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return parseJsonApiResponse<SymbolMapping>(response);
  },

  async delete(id: number): Promise<void> {
    const response = await fetch(`${API_URL}/${id}`, { method: 'DELETE' });
    await parseJsonApiResponse<{ deleted: boolean }>(response);
  },
};
