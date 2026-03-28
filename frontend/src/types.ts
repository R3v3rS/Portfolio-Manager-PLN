export interface Portfolio {
  id: number;
  name: string;
  account_type: 'STANDARD' | 'IKE' | 'BONDS' | 'SAVINGS' | 'PPK';
  current_cash: number;
  total_deposits: number;
  savings_rate: number;
  last_interest_date?: string;
  created_at?: string;
  parent_portfolio_id?: number | null;
  is_archived?: boolean;
  children?: Portfolio[];
  portfolio_value?: number;
  cash_value?: number;
  holdings_value?: number;
  total_dividends?: number;
  open_positions_result?: number;
  total_result?: number;
  total_result_percent?: number;
  is_empty?: boolean;
}

export interface Transaction {
  id: number;
  portfolio_id: number;
  sub_portfolio_id?: number | null;
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
  sub_portfolio_id?: number | null;
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
  price_last_updated_at?: string | null;
}

export interface PortfolioValue {
  portfolio_value: number;
  cash_value: number;
  holdings_value: number;
  total_dividends: number;
  total_interest?: number;
  open_positions_result: number;
  total_result: number;
  total_result_percent: number;
  xirr_percent?: number;
  change_1d?: number;
  change_1d_percent?: number;
  change_7d?: number;
  change_7d_percent?: number;
}

export interface ClosedPosition {
  ticker: string;
  company_name?: string | null;
  realized_profit: number;
  invested_capital: number;
  profit_percent_on_capital?: number | null;
  last_sell_date?: string | null;
}


export interface ClosedPositionCycle {
  ticker: string;
  company_name?: string | null;
  cycle_id: number;
  opened_at?: string | null;
  closed_at?: string | null;
  realized_profit: number;
  invested_capital: number;
  average_invested_capital?: number | null;
  holding_period_days?: number | null;
  profit_percent_on_capital?: number | null;
  annualized_return_percent?: number | null;
  buy_count?: number;
  sell_count?: number;
  status?: 'CLOSED' | 'PARTIALLY_CLOSED';
  is_partially_closed?: boolean;
  remaining_quantity?: number;
}

export interface EquityAllocation {
  ticker: string;
  name: string;
  value: number;
  percentage: number;
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
  score: number | null;
  quantity: number;
  is_watched: boolean;
  last_updated_at: string | null;
}

export interface StockAnalysisData {
  score: number | null;
  details: {
    quality: number | null;
    growth: number | null;
    risk: number | null;
  };
  fundamentals: {
    trailingPE: number | null;
    priceToBook: number | null;
    returnOnEquity: number | null;
    payoutRatio: number | null;
    operatingMargins: number | null;
    profitMargins: number | null;
    returnOnAssets: number | null;
    freeCashflow: number | null;
    operatingCashflow: number | null;
  };
  growth: {
    revenueGrowth: number | null;
    earningsGrowth: number | null;
    earningsQuarterlyGrowth: number | null;
  };
  risk: {
    debtToEquity: number | null;
    currentRatio: number | null;
    quickRatio: number | null;
    beta: number | null;
  };
  market: {
    heldPercentInstitutions: number | null;
    heldPercentInsiders: number | null;
    shortPercentOfFloat: number | null;
    shortRatio: number | null;
    averageVolume: number | null;
    volume: number | null;
    fiftyTwoWeekLow: number | null;
    fiftyTwoWeekHigh: number | null;
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
