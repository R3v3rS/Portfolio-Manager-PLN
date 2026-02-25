export interface Portfolio {
  id: number;
  name: string;
  current_cash: number;
  total_deposits: number;
  created_at?: string;
  portfolio_value?: number;
  cash_value?: number;
  holdings_value?: number;
  total_result?: number;
  total_result_percent?: number;
}

export interface Transaction {
  id: number;
  portfolio_id: number;
  ticker: string;
  date: string;
  type: 'BUY' | 'SELL' | 'DEPOSIT' | 'WITHDRAW';
  quantity: number;
  price: number;
  total_value: number;
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
}

export interface PortfolioValue {
  portfolio_value: number;
  cash_value: number;
  holdings_value: number;
  total_result: number;
  total_result_percent: number;
}
