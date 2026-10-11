import { createApiClient } from './apiConfig';

export interface ReportBudget {
  budget_spent?:number; budget_net?:number; reserve_contributions?:number; reserve_released?:number; reserve_settled?:number;
  income: number; expenses: number; net: number; balance_adjustments?:number; balance_checks?:number;
  transfer_to_investments: number; transfer_from_investments: number;
  entry_count: number; receipt_count: number; planned: number;
  categories: { id: number | null; name: string; parent_id?: number | null; direct_spent?: number; planned: number; spent: number; difference: number }[];
}
interface WealthSnapshot { date: string; net_worth: number; total_assets: number; total_liabilities: number; assets_breakdown?: Record<string, number> | null; valuation_notes?: string[] }
export interface MonthlyReportData {
  schema_version: number; month: string; generated_at: string;
  period: { start: string; end: string; partial: boolean; previous_start: string; previous_end: string };
  budget: ReportBudget & { previous: ReportBudget; changes: { income: number; expenses: number; net: number } };
  investments: {
    operations: { count: number; buys: number; sells: number; deposits: number; withdrawals: number; internal_transfers: number; dividends: number; interest: number; commissions: number; realized_profit: number };
    performance: { profit: number | null; available_profit?: number; valued_count?: number; complete: boolean; excluded_count: number; archived_count: number; items: {
      id: number; name: string; account_type: string; opening_value: number | null; closing_value: number | null;
      profit: number | null; estimated_profit?: number | null; basis?: string; return_percent: number | null; status: string; warnings: string[];
    }[] };
    ppk: { count: number; employee_contributions: number; employer_contributions: number };
  };
  loans: { paid_amount: number; overpaid_amount: number; without_record: number; items: {
    id: number; name: string; scheduled_count: number | null; scheduled_amount: number | null;
    without_record: number | null; estimated_balance: number | null; paid_count: number;
    paid_amount: number; overpaid_amount: number; budget_linked_amount: number;
  }[] };
  wealth: { opening: WealthSnapshot | null; closing: WealthSnapshot | null; latest: WealthSnapshot | null; change: number | null; observations: number; history?: WealthSnapshot[]; history_start?: string; observed_change?: number | null };
  journal: {
    entries: { id: number; title: string; ticker: string | null; kind: string; status: string; entry_date: string; is_archived: number }[];
    reviews: { id: number; entry_id: number; review_date: string; outcome: string; notes: string; lessons: string; title: string; ticker: string | null }[];
    due: { id: number; title: string; ticker: string | null; review_date: string }[];
  };
  completed_tasks: { id: number; title: string; category: string; completed_at: string }[];
  insights: { tone: string; text: string; href: string; label: string }[];
  warnings: string[];
}
const http = createApiClient('/dashboard');
export const monthlyReportApi = { get: (month: string) => http.get<MonthlyReportData>(`/monthly-report?month=${encodeURIComponent(month)}`) };
