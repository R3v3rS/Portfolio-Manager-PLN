import { createHttpClient } from './http';
import { RadarItem, StockAnalysisData } from './types';

const api = createHttpClient('/api/radar');

export const radarApi = {
  getAll: (refresh = false): Promise<RadarItem[]> =>
    api.get('/', { params: { refresh: refresh ? 1 : undefined } }),

  refresh: (tickers?: string[]): Promise<void> =>
    api.post('/refresh', { tickers: tickers ?? [] }),

  addToWatchlist: (ticker: string): Promise<void> =>
    api.post('/watchlist', { ticker }),

  removeFromWatchlist: async (ticker: string): Promise<void> => {
    await api.delete(`/watchlist/${ticker}`);
  },

  getAnalysis: (ticker: string): Promise<StockAnalysisData> =>
    api.get(`/analysis/${ticker}`),
};
