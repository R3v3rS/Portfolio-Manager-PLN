import { buildApiPath, createApiClient } from './apiConfig';
import type { PlanningWorkspace } from './api_planning';

const client = createApiClient('/budget/workspace');

export type BudgetAccount = { id: number; name: string; balance: number; currency: string };
export type BudgetCategory = {
  id: number; name: string; icon: string; manual_plan: number;
  planned_bills: number; planned: number; spent: number; remaining: number;
  monthly_reserve_plan?:number; monthly_reserve_managed?:boolean; actual_spent?:number;
  is_unassigned?: boolean; parent_id?: number | null; parent_name?: string | null;
  path?: string; selection_label?: string; version?: number; has_children?: boolean;
  direct_spent?: number; direct_planned_bills?: number; children_plan?: number;
  carryover?: number; reserve_covered?:number; reserve_settled?:number;
};
export type BudgetLine = { category_id: number; category_name: string; label: string; amount: number };
export type BudgetEntry = {
  id: number; account_id: number; account_name: string; kind: 'INCOME' | 'EXPENSE' | 'TRANSFER' | 'REFUND';
  refund_of?:number|null; refunded?:number;reserve_id?:number|null;
  direction?: 'IN' | 'OUT'; portfolio_id?: number; portfolio_name?: string;
  investment_transaction_id?: number;
  amount: number; date: string; description: string; merchant: string | null;
  has_receipt: boolean; bill_id: number | null; loan_id: number | null; lines: BudgetLine[];
  version?: number; cash_effect?: boolean; classification_status?: 'UNASSIGNED' | 'GENERAL' | 'SPLIT';
};
export type BudgetBill = {
  planned_amount?:number;paid_on?:string|null;
  reserve_covered?:number; unfunded?:number; funding_source?:string;
  id: number; title: string; amount: number; due_date: string; frequency: 'MONTHLY' | 'QUARTERLY' | 'YEARLY' | 'ONCE';
  category_id: number; category_name: string; account_id: number; account_name: string;
  status: 'PAID' | 'UPCOMING' | 'OVERDUE'; entry_id: number | null;
  base_amount?:number; active?:boolean; version?:number; start_month?:string|null; end_month?:string|null; due_month?:string|null; due_day?:number;
  promotion_end?:string|null; notice_date?:string|null; regular_amount?:number|null; variable_amount?:boolean; notes?:string;
  reserve_id?:number|null; reserve_name?:string|null; reserve_version?:number|null; annual_cost?:number;
  next_due_date?:string|null;
  payment_candidates?:{id:number;date:string;description:string;amount:number;version:number}[];
};
export type BudgetWorkspace = {
  chart?:{date:string;cash_spent:number|null;budget_spent:number|null;cash_plan:number;budget_plan:number;daily_spent?:number|null;daily_plan?:number}[];
  fixed_costs?:{planned:number;paid:number;pending:number;over_plan:number;early_count:number;paid_count:number;count:number};
  month: string; accounts: BudgetAccount[]; categories: BudgetCategory[];
  bills: BudgetBill[]; entries: BudgetEntry[];
  planning?: PlanningWorkspace;
  totals: {
    period_spending?: {
      first: string; through: string | null; spent: number; expense_count: number;
      reserve_contributions: number; reserve_released: number; reserve_settled: number;
      reserve_adjustment: number; budget_spent: number;
      refunds?:number;
    };
    balance: number; income: number; planned: number; spent: number;
    remaining_in_plan: number; to_plan: number;
    expected_income?: number;
    monthly_income_total?:number;monthly_income_cost?:number;monthly_income_remaining_plan?:number;
    monthly_income_to_plan?:number;monthly_invested?:number;
    refunds?:number; remaining_commitments?:number; loan_warnings?:string[];
    available_now?:number; reserve_plan_remaining?:number;reserve_plan_extra?:number;
    reserved?: number;
    budget_spent?:number; budget_net?:number; reserve_contributions?:number; reserve_released?:number; reserve_settled?:number;
  };
};
export type EntryInput = {
  request_id?:string;
  version?: number;
  account_id: number; kind: 'INCOME' | 'EXPENSE'; amount: number;
  date: string; description: string; merchant?: string;
  lines?: { category_id: number; amount: number; label?: string }[];
};
export type BillInput = {
  title: string; account_id: number; category_id: number; amount: number;
  due_day: number; frequency: 'MONTHLY' | 'QUARTERLY' | 'YEARLY' | 'ONCE'; due_month?: string; start_month?: string;
  end_month?:string|null; promotion_end?:string|null; notice_date?:string|null; regular_amount?:number|null; variable_amount?:boolean;
  reserve_id?:number|null; notes?:string; version?:number; request_id?:string;
  active?:boolean;
};

export const budgetWorkspaceApi = {
  settlementPreview:(id:number)=>client.get<SettlementPreview>(`/entries/${id}/settlement-preview`),
  reverseSettlement:(id:number,input:SettlementPreview,request_id:string)=>client.post(`/entries/${id}/reverse-settlement`,{...input,request_id}),
  get: (month: string) => client.get<BudgetWorkspace>('', { params: { month } }),
  createAccount: (name: string, balance: number) => client.post<{ id: number }>('/accounts', { name, balance }),
  createCategory: (name: string, parent_id: number | null = null) => client.post<{ id: number }>('/categories', { name, parent_id }),
  updateCategory: (id: number, name: string, parent_id: number | null, version: number) => client.put<{ id: number }>('/categories/' + id, { name, parent_id, version }),
  setPlan: (categoryId: number, month: string, amount: number) =>
    client.put('/plans/' + categoryId, { month, amount }),
  copyPlans: (source: string, target: string) => client.post<{ copied: number }>('/plans/copy', { source, target }),
  createEntry: (entry: EntryInput) => client.post<{ id: number }>('/entries', entry),
  updateEntry: (id: number, entry: EntryInput) => client.put('/entries/' + id, entry),
  applyEntryBalance: (id: number, version: number, expected_balance: number) =>
    client.post<{id:number;cash_effect:boolean;applied:boolean;version:number;balance:number}>(`/entries/${id}/apply-balance`, {version,expected_balance}),
  deleteEntry: (id: number) => client.delete('/entries/' + id),
  refund:(id:number,input:{version:number;amount:number;date:string;account_id:number;category_id?:number;lines?:{category_id:number;amount:number;label:string}[];balance_mode:'APPLY'|'HISTORY';expected_balance:number;existing_entry_id?:number;entry_version?:number},request_id:string)=>client.post<{id:number}>(`/entries/${id}/refunds`,{...input,request_id}),
  createBill: (bill: BillInput) => client.post<{ id: number }>('/bills', bill),
  updateBill: (id:number,bill:BillInput) => client.put('/bills/'+id,bill),
  deleteBill: (id: number) => client.delete('/bills/' + id),
  payBill: (id: number, month: string, date: string,details:{amount?:number;version?:number;reserve_version?:number;request_id?:string;existing_entry_id?:number;entry_version?:number;confirm_separate?:boolean;expected_balance?:number}={}) =>
    client.post<{ entry_id: number }>('/bills/' + id + '/pay', { month, date,...details }),
  uploadReceipt: (id: number, file: File) => {
    const data = new FormData();
    data.append('file', file);
    return client.post<{ entry_id: number; has_receipt: boolean }>('/entries/' + id + '/receipt', data);
  },
  receiptUrl: (id: number) => buildApiPath('/budget/workspace/entries/' + id + '/receipt'),
};

export interface SettlementPreview {entry_id:number;entry_version:number;reserve_version:number|null;balance_before:number;balance_after:number;account_name:string;delete_expense:boolean;restored_reserve:number;message:string}
