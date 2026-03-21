import { createApiClient } from './apiConfig';

const symbolMapHttp = createApiClient('/symbol-map');

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

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);

const normalizeSymbolMapping = (value: unknown): SymbolMapping => {
  const source = isRecord(value) ? value : {};
  const currency = source.currency;

  return {
    id: typeof source.id === 'number' ? source.id : Number(source.id ?? 0),
    symbol_input: typeof source.symbol_input === 'string' ? source.symbol_input : '',
    ticker: typeof source.ticker === 'string' ? source.ticker : '',
    currency: currency === 'PLN' || currency === 'USD' || currency === 'EUR' || currency === 'GBP' ? currency : null,
    created_at: typeof source.created_at === 'string' ? source.created_at : null,
  };
};

export const symbolMapApi = {
  getAll: async (): Promise<SymbolMapping[]> => {
    const response = await symbolMapHttp.get<unknown>('');
    return Array.isArray(response) ? response.map(normalizeSymbolMapping) : [];
  },
  create: async (payload: CreateSymbolMappingPayload): Promise<SymbolMapping> => {
    const response = await symbolMapHttp.post<unknown>('', payload);
    return normalizeSymbolMapping(response);
  },
  update: async (id: number, payload: UpdateSymbolMappingPayload): Promise<SymbolMapping> => {
    const response = await symbolMapHttp.put<unknown>(`/${id}`, payload);
    return normalizeSymbolMapping(response);
  },
  delete: async (id: number): Promise<void> => {
    await symbolMapHttp.delete(`/${id}`);
  },
};
