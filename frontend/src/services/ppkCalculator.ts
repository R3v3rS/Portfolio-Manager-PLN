export interface PPKTransaction {
  id: number;
  portfolio_id: number;
  date: string;
  employee_units: number;
  employer_units: number;
  price_per_unit: number;
}

export interface PPKSummary {
  totalUnits: number;
  averagePrice: number;
  totalContribution: number;
  currentValue: number;
  profit: number;
  tax: number;
  netProfit: number;
}
