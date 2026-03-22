import { createApiClient } from './apiConfig';
import { RadarItem, StockAnalysisData } from './types';

const radarHttp = createApiClient('/radar');

interface RadarActionResult {
  message: string;
  tickers: string[];
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const toNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
};

const toString = (value: unknown, fallback = ''): string => {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return fallback;
  return String(value);
};

const toNullableString = (value: unknown): string | null => {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  return normalized || null;
};

const toBoolean = (value: unknown): boolean => value === true;

const normalizeRadarItem = (value: unknown): RadarItem => {
  const source = isRecord(value) ? value : {};

  return {
    ticker: toString(source.ticker),
    price: toNumber(source.price),
    change_1d: toNumber(source.change_1d),
    change_7d: toNumber(source.change_7d),
    change_1m: toNumber(source.change_1m),
    change_1y: toNumber(source.change_1y),
    next_earnings: toNullableString(source.next_earnings),
    ex_dividend_date: toNullableString(source.ex_dividend_date),
    dividend_yield: toNumber(source.dividend_yield),
    score: toNumber(source.score),
    quantity: toNumber(source.quantity) ?? 0,
    is_watched: toBoolean(source.is_watched),
    last_updated_at: toNullableString(source.last_updated_at),
  };
};

const normalizeAnalysisData = (value: unknown): StockAnalysisData => {
  const source = isRecord(value) ? value : {};
  const details = isRecord(source.details) ? source.details : {};
  const fundamentals = isRecord(source.fundamentals) ? source.fundamentals : {};
  const growth = isRecord(source.growth) ? source.growth : {};
  const risk = isRecord(source.risk) ? source.risk : {};
  const market = isRecord(source.market) ? source.market : {};
  const analyst = isRecord(source.analyst) ? source.analyst : {};
  const technicals = isRecord(source.technicals) ? source.technicals : {};

  return {
    score: toNumber(source.score),
    details: {
      quality: toNumber(details.quality),
      growth: toNumber(details.growth),
      risk: toNumber(details.risk),
    },
    fundamentals: {
      trailingPE: toNumber(fundamentals.trailingPE),
      priceToBook: toNumber(fundamentals.priceToBook),
      returnOnEquity: toNumber(fundamentals.returnOnEquity),
      payoutRatio: toNumber(fundamentals.payoutRatio),
      operatingMargins: toNumber(fundamentals.operatingMargins),
      profitMargins: toNumber(fundamentals.profitMargins),
      returnOnAssets: toNumber(fundamentals.returnOnAssets),
      freeCashflow: toNumber(fundamentals.freeCashflow),
      operatingCashflow: toNumber(fundamentals.operatingCashflow),
    },
    growth: {
      revenueGrowth: toNumber(growth.revenueGrowth),
      earningsGrowth: toNumber(growth.earningsGrowth),
      earningsQuarterlyGrowth: toNumber(growth.earningsQuarterlyGrowth),
    },
    risk: {
      debtToEquity: toNumber(risk.debtToEquity),
      currentRatio: toNumber(risk.currentRatio),
      quickRatio: toNumber(risk.quickRatio),
      beta: toNumber(risk.beta),
    },
    market: {
      heldPercentInstitutions: toNumber(market.heldPercentInstitutions),
      heldPercentInsiders: toNumber(market.heldPercentInsiders),
      shortPercentOfFloat: toNumber(market.shortPercentOfFloat),
      shortRatio: toNumber(market.shortRatio),
      averageVolume: toNumber(market.averageVolume),
      volume: toNumber(market.volume),
      fiftyTwoWeekLow: toNumber(market.fiftyTwoWeekLow),
      fiftyTwoWeekHigh: toNumber(market.fiftyTwoWeekHigh),
    },
    analyst: {
      targetMeanPrice: toNumber(analyst.targetMeanPrice),
      recommendationKey: toNullableString(analyst.recommendationKey),
      upsidePotential: toNumber(analyst.upsidePotential),
    },
    technicals: {
      sma50: toNumber(technicals.sma50),
      sma200: toNumber(technicals.sma200),
      rsi14: toNumber(technicals.rsi14),
    },
  };
};

const normalizeActionResult = (value: unknown, fallbackMessage: string): RadarActionResult => {
  const source = isRecord(value) ? value : {};

  return {
    message: typeof source.message === 'string' && source.message.trim() ? source.message : fallbackMessage,
    tickers: Array.isArray(source.tickers) ? source.tickers.map((ticker) => toString(ticker)).filter(Boolean) : [],
  };
};

export const radarApi = {
  getAll: async (refresh = false): Promise<RadarItem[]> => {
    const response = await radarHttp.get<unknown>('/', { params: { refresh: refresh ? 1 : undefined } });
    return Array.isArray(response) ? response.map(normalizeRadarItem).filter((item) => Boolean(item.ticker)) : [];
  },

  refresh: async (tickers?: string[]): Promise<RadarActionResult> => {
    const response = await radarHttp.post<unknown>('/refresh', { tickers: tickers ?? [] });
    return normalizeActionResult(response, 'Odświeżono radar.');
  },

  addToWatchlist: async (ticker: string): Promise<RadarActionResult> => {
    const response = await radarHttp.post<unknown>('/watchlist', { ticker });
    return normalizeActionResult(response, 'Dodano ticker do obserwowanych.');
  },

  removeFromWatchlist: async (ticker: string): Promise<RadarActionResult> => {
    const response = await radarHttp.delete<unknown>(`/watchlist/${ticker}`);
    return normalizeActionResult(response, 'Usunięto ticker z obserwowanych.');
  },

  getAnalysis: async (ticker: string): Promise<StockAnalysisData> => {
    const response = await radarHttp.get<unknown>(`/analysis/${ticker}`);
    return normalizeAnalysisData(response);
  },
};
