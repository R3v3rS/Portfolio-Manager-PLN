export interface Portfolio {
  id: number;
  name: string;
  account_type: 'STANDARD' | 'IKE' | 'BONDS' | 'SAVINGS' | 'PPK';
  current_cash: number;
  total_deposits: number;
  savings_rate: number;
  last_interest_date?: string;
  created_at?: string;
  portfolio_value?: number;
  cash_value?: number;
  holdings_value?: number;
  total_dividends?: number;
  total_result?: number;
  total_result_percent?: number;
}

export interface Transaction {
  id: number;
  portfolio_id: number;
  ticker: string;
  date: string;
  type: 'BUY' | 'SELL' | 'DEPOSIT' | 'WITHDRAW' | 'DIVIDEND' | 'INTEREST';
  quantity: number;
  price: number;
  total_value: number;
  realized_profit?: number;
  commission?: number;
}

export interface Bond {
  id: number;
  portfolio_id: number;
  name: string;
  principal: number;
  interest_rate: number;
  purchase_date: string;
  accrued_interest: number;
  total_value: number;
}

export interface Dividend {
  id: number;
  portfolio_id: number;
  ticker: string;
  amount: number;
  date: string;
}

export interface Holding {
  id: number;
  portfolio_id: number;
  ticker: string;
  quantity: number;
  average_buy_price: number;
  total_cost: number;
  current_price?: number; 
  current_value?: number;
  profit_loss?: number;
  profit_loss_percent?: number;
  weight_percent?: number;
  company_name?: string;
  sector?: string;
  industry?: string;
  auto_fx_fees?: boolean;
  fx_rate_used?: number;
  currency?: string;
}

export interface PortfolioValue {
  portfolio_value: number;
  cash_value: number;
  holdings_value: number;
  total_dividends: number;
  total_result: number;
  total_result_percent: number;
  xirr_percent?: number;
}

export interface ClosedPosition {
  ticker: string;
  company_name?: string | null;
  realized_profit: number;
}

export interface RadarItem {
  ticker: string;
  price: number | null;
  change_1d: number | null;
  change_7d: number | null;
  change_1m: number | null;
  change_1y: number | null;
  next_earnings: string | null;
  ex_dividend_date: string | null;
  dividend_yield: number | null;
  quantity: number;
  is_watched: boolean;
  last_updated_at: string | null;
}

export interface StockAnalysisData {
  fundamentals: {
    trailingPE: number | null;
    priceToBook: number | null;
    returnOnEquity: number | null;
    payoutRatio: number | null;
  };
  analyst: {
    targetMeanPrice: number | null;
    recommendationKey: string | null;
    upsidePotential: number | null;
  };
  technicals: {
    sma50: number | null;
    sma200: number | null;
    rsi14: number | null;
  };
}
