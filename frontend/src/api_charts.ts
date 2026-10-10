import { createApiClient } from './apiConfig';
const portfolio = createApiClient('/portfolio');
const dashboard = createApiClient('/dashboard');
export type PerformanceMatrix = Record<string, Record<string, number | null>>;
export type Attribution = { items: { ticker: string; value: number; dividends: number }[]; missing_tickers?: string[]; status: string; from: string; to: string };
export type WealthPoint = { date: string; net_worth: number; total_assets: number; total_liabilities: number };
export const chartsApi = {
  performance: (id: number) => portfolio.get<{ matrix: PerformanceMatrix }>(`/${id}/performance`),
  benchmark:(id:number,start:string,end:string,ticker:string)=>portfolio.get<{items:{date:string;value:number|null}[]}>(`/history/benchmark/${id}`,{params:{from:start,to:end,ticker}}),
  attribution: (id: number, start: string, end: string) => portfolio.get<Attribution>(`/history/attribution/${id}`, { params: { from: start, to: end } }),
  wealth: () => dashboard.get<{ history: WealthPoint[] }>('/net-worth-history'),
};
