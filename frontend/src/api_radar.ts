import { RadarItem, StockAnalysisData } from './types';
import { http } from './lib/http';

export const radarApi = {
  getItems: (refresh = false) =>
    http.get<RadarItem[]>('/api/radar', { params: refresh ? { refresh: 1 } : undefined }),

  refresh: (tickers: string[] = []) => http.post('/api/radar/refresh', { tickers }),

  addToWatchlist: (ticker: string) => http.post('/api/radar/watchlist', { ticker: ticker.toUpperCase() }),

  removeFromWatchlist: (ticker: string) => http.delete(`/api/radar/watchlist/${ticker}`),

  getAnalysis: (ticker: string) => http.get<StockAnalysisData>(`/api/radar/analysis/${ticker}`),
};
