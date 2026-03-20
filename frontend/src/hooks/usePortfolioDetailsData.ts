import { useCallback, useState } from 'react';
import api from '../api';
import { budgetApi, BudgetAccount } from '../api_budget';
import { Bond, ClosedPosition, ClosedPositionCycle, Holding, Portfolio, PortfolioValue, Transaction } from '../types';
import { PPKSummary, PPKTransaction as PPKTx } from '../services/ppkCalculator';

interface PortfolioListResponse { portfolios: Portfolio[] }
interface HoldingsResponse { holdings: Holding[] }
interface PortfolioValueResponse extends PortfolioValue { live_interest?: number }
interface MonthlyDividendsResponse { monthly_dividends: { label: string; amount: number }[] }
interface TransactionsResponse { transactions: Transaction[] }
interface ClosedPositionsResponse { positions: ClosedPosition[]; total_historical_profit: number }
interface ClosedPositionCyclesResponse { positions: ClosedPositionCycle[]; total_historical_profit?: number }
interface BondsResponse { bonds: Bond[] }
interface HistorySeriesPoint { date: string; label: string; value: number; benchmark_value?: number }
interface PortfolioHistoryResponse { history: HistorySeriesPoint[] }
interface PpkResponse { transactions?: PPKTx[]; summary?: PPKSummary | null; currentPrice?: { price: number; date: string } | null }

export interface PortfolioDetailsDataState {
  portfolio: Portfolio | null;
  holdings: Holding[];
  bonds: Bond[];
  ppkTransactions: PPKTx[];
  ppkSummary: PPKSummary | null;
  ppkCurrentPrice: { price: number; date: string } | null;
  valueData: PortfolioValueResponse | null;
  portfolioTransactions: Transaction[];
  monthlyDividends: { label: string; amount: number }[];
  portfolioHistory: HistorySeriesPoint[];
  portfolioProfitHistory: { date: string; label: string; value: number }[];
  portfolioProfit30dHistory: { date: string; label: string; value: number }[];
  portfolioValue30dHistory: { date: string; label: string; value: number }[];
  closedPositions: ClosedPosition[];
  totalClosedProfit: number;
  closedPositionCycles: ClosedPositionCycle[];
  totalClosedCyclesProfit: number;
  budgetAccounts: BudgetAccount[];
}

const initialState: PortfolioDetailsDataState = {
  portfolio: null,
  holdings: [],
  bonds: [],
  ppkTransactions: [],
  ppkSummary: null,
  ppkCurrentPrice: null,
  valueData: null,
  portfolioTransactions: [],
  monthlyDividends: [],
  portfolioHistory: [],
  portfolioProfitHistory: [],
  portfolioProfit30dHistory: [],
  portfolioValue30dHistory: [],
  closedPositions: [],
  totalClosedProfit: 0,
  closedPositionCycles: [],
  totalClosedCyclesProfit: 0,
  budgetAccounts: [],
};

export const usePortfolioDetailsData = (portfolioId?: string) => {
  const [data, setData] = useState<PortfolioDetailsDataState>(initialState);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    if (!portfolioId) return;

    setLoading(true);
    try {
      const [portfolios, holdings, value, monthlyDividends, transactions, closedPositions, closedCycles, budgetSummary] = await Promise.all([
        api.get<PortfolioListResponse>('/list'),
        api.get<HoldingsResponse>(`/holdings/${portfolioId}`),
        api.get<PortfolioValueResponse>(`/value/${portfolioId}`),
        api.get<MonthlyDividendsResponse>(`/dividends/monthly/${portfolioId}`),
        api.get<TransactionsResponse>(`/transactions/${portfolioId}`),
        api.get<ClosedPositionsResponse>(`/${portfolioId}/closed-positions`),
        api.get<ClosedPositionCyclesResponse>(`/${portfolioId}/closed-position-cycles`),
        budgetApi.getSummary(),
      ]);

      const portfolio = portfolios.data.portfolios.find((item) => item.id === Number(portfolioId)) ?? null;

      let bonds: Bond[] = [];
      let ppkTransactions: PPKTx[] = [];
      let ppkSummary: PPKSummary | null = null;
      let ppkCurrentPrice: { price: number; date: string } | null = null;
      let portfolioHistory: HistorySeriesPoint[] = [];
      let portfolioProfitHistory: { date: string; label: string; value: number }[] = [];
      let portfolioProfit30dHistory: { date: string; label: string; value: number }[] = [];
      let portfolioValue30dHistory: { date: string; label: string; value: number }[] = [];

      if (portfolio?.account_type === 'BONDS') {
        const response = await api.get<BondsResponse>(`/bonds/${portfolioId}`);
        bonds = response.data.bonds;
      }

      if (portfolio?.account_type === 'SAVINGS') {
        const response = await api.get<PortfolioHistoryResponse>(`/history/monthly/${portfolioId}`);
        portfolioHistory = response.data.history;
      }

      if (portfolio?.account_type === 'PPK') {
        const response = await api.get<PpkResponse>(`/ppk/transactions/${portfolioId}`);
        ppkTransactions = response.data.transactions || [];
        ppkSummary = response.data.summary || null;
        ppkCurrentPrice = response.data.currentPrice || null;
      }

      if (portfolio && portfolio.account_type !== 'BONDS' && portfolio.account_type !== 'SAVINGS') {
        const [history, profit, profit30d, value30d] = await Promise.all([
          api.get<PortfolioHistoryResponse>(`/history/monthly/${portfolioId}`),
          api.get<PortfolioHistoryResponse>(`/history/profit/${portfolioId}`),
          api.get<PortfolioHistoryResponse>(`/history/profit/${portfolioId}?days=30`),
          api.get<PortfolioHistoryResponse>(`/history/value/${portfolioId}?days=30`),
        ]);
        portfolioHistory = history.data.history;
        portfolioProfitHistory = profit.data.history;
        portfolioProfit30dHistory = profit30d.data.history || [];
        portfolioValue30dHistory = value30d.data.history || [];
      }

      setData({
        portfolio,
        holdings: holdings.data.holdings,
        bonds,
        ppkTransactions,
        ppkSummary,
        ppkCurrentPrice,
        valueData: value.data,
        portfolioTransactions: transactions.data.transactions,
        monthlyDividends: monthlyDividends.data.monthly_dividends,
        portfolioHistory,
        portfolioProfitHistory,
        portfolioProfit30dHistory,
        portfolioValue30dHistory,
        closedPositions: closedPositions.data.positions,
        totalClosedProfit: closedPositions.data.total_historical_profit,
        closedPositionCycles: closedCycles.data.positions || [],
        totalClosedCyclesProfit: closedCycles.data.total_historical_profit || 0,
        budgetAccounts: budgetSummary.accounts || [],
      });

      return portfolio;
    } finally {
      setLoading(false);
    }
  }, [portfolioId]);

  const refreshMarketData = useCallback(async () => {
    if (!portfolioId) return null;

    const [holdingsResponse, valueResponse] = await Promise.all([
      api.get<HoldingsResponse>(`/holdings/${portfolioId}?refresh=1`),
      api.get<PortfolioValueResponse>(`/value/${portfolioId}`),
    ]);

    setData((current) => ({
      ...current,
      holdings: holdingsResponse.data.holdings || [],
      valueData: valueResponse.data,
    }));

    return {
      holdings: holdingsResponse.data.holdings || [],
      valueData: valueResponse.data,
    };
  }, [portfolioId]);

  const fetchTickerHistory = useCallback(async (ticker: string) => {
    const response = await api.get<{ history: { date: string; close_price: number }[]; last_updated: string | null }>(`/history/${ticker}`);
    return response.data;
  }, []);

  const fetchBenchmarkHistory = useCallback(async (benchmark: string) => {
    if (!portfolioId) return null;
    const historyUrl = benchmark ? `/history/monthly/${portfolioId}?benchmark=${benchmark}` : `/history/monthly/${portfolioId}`;
    const [historyResponse, profitResponse] = await Promise.all([
      api.get<PortfolioHistoryResponse>(historyUrl),
      api.get<PortfolioHistoryResponse>(`/history/profit/${portfolioId}`),
    ]);

    setData((current) => ({
      ...current,
      portfolioHistory: historyResponse.data.history,
      portfolioProfitHistory: profitResponse.data.history,
    }));

    return {
      portfolioHistory: historyResponse.data.history,
      portfolioProfitHistory: profitResponse.data.history,
    };
  }, [portfolioId]);

  return { data, loading, fetchAll, refreshMarketData, fetchTickerHistory, fetchBenchmarkHistory };
};
