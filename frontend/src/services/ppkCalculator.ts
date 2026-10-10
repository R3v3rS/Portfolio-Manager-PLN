export interface PPKTransaction {
  id: number;
  portfolio_id: number;
  date: string;
  employee_units: number;
  employer_units: number;
  price_per_unit: number;
}

export interface PPKSummary {
  withdrawalTax?: number | null;
  employerToZUS?: number | null;
  withdrawalResult?: number | null;
  totalUnits: number;
  averagePrice: number;
  totalContribution: number;
  currentValue: number | null;
  profit: number | null;
  tax: number | null;
  netProfit: number | null;
  totalPurchaseValue: number;
  totalCurrentValue: number | null;
  totalNetValue: number | null;
  totalTax: number | null;
  totalProfit: number | null;
}
