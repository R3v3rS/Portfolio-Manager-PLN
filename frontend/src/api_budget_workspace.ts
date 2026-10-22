import { buildApiPath, createApiClient } from './apiConfig';
import type { PlanningWorkspace } from './api_planning';

const client = createApiClient('/budget/workspace');

export type BudgetAccount = { id: number; name: string; balance: number; currency: string; account_type?:'BANK'|'CREDIT_CARD' };
export type BudgetCategory = {
  plan_source?:'DEFAULT'|'MONTH'|'MEDIA'|'NONE'; plan_source_month?:string|null; default_plan?:number|null;
  plan_details?: {ordinary_planned:number;ordinary_spent:number;ordinary_remaining:number;payments_planned:number;payments_pending:number;media_remaining:number;ordinary_over:number};
  id: number; name: string; icon: string; manual_plan: number;
  planned_bills: number; planned: number; spent: number; remaining: number;
  monthly_reserve_plan?:number; monthly_reserve_managed?:boolean; actual_spent?:number;
  is_unassigned?: boolean; parent_id?: number | null; parent_name?: string | null;
  path?: string; selection_label?: string; version?: number; has_children?: boolean;
  direct_spent?: number; direct_planned_bills?: number; children_plan?: number;
  carryover?: number; reserve_covered?:number; reserve_settled?:number;
  daily_pace_included?:boolean; daily_pace_effective?:boolean;
  description?:string; has_activity?:boolean; rule_count?:number;
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
  bank_transfers?:{id:number;date:string;description:string;amount:number;source_account_id:number;target_account_id:number;source_name:string;target_name:string;reserve_name:string|null;move_money?:number;reserve_action?:string}[];
  chart?:{date:string;cash_spent:number|null;budget_spent:number|null;cash_plan:number;budget_plan:number;daily_spent?:number|null;daily_plan?:number}[];
  fixed_costs?:{planned:number;paid:number;pending:number;over_plan:number;early_count:number;paid_count:number;count:number};
  month: string; accounts: BudgetAccount[]; categories: BudgetCategory[];
  bills: BudgetBill[]; entries: BudgetEntry[];
  planning?: PlanningWorkspace;
  totals: {
    cash_balance?:number;credit_card_debt?:number;credit_card_overpayment?:number;
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
  yearPlan:(start:string)=>client.get<BudgetYearPlan>('/plans/year',{params:{start}}),
  previewTransfer:(input:PlanTransferInput)=>client.post<PlanTransferPreview>('/plans/transfer-preview',input),
  transferPlan:(input:PlanTransferInput,token:string,request_id:string)=>client.post<PlanTransferPreview>('/plans/transfer',{...input,token,request_id}),
  defaultPlans:(month:string)=>client.get<DefaultPlans>('/plans/defaults',{params:{month}}),
  saveDefaults:(start_month:string,items:{category_id:number;amount:number;revision:string}[])=>client.put<{saved:number}>('/plans/defaults',{start_month,items}),
  resetPlan:(categoryId:number,month:string)=>client.delete('/plans/'+categoryId,{params:{month}}),
  previewCopy:(input:PlanCopyInput)=>client.post<PlanCopyPreview>('/plans/copy-preview',input),
  copyRange:(input:PlanCopyInput,token:string,request_id:string)=>client.post<{copied:number;skipped:number}>('/plans/copy-range',{...input,token,request_id}),
  settlementPreview:(id:number)=>client.get<SettlementPreview>(`/entries/${id}/settlement-preview`),
  reverseSettlement:(id:number,input:SettlementPreview,request_id:string)=>client.post(`/entries/${id}/reverse-settlement`,{...input,request_id}),
  get: (month: string) => client.get<BudgetWorkspace>('', { params: { month } }),
  createAccount: (name: string, balance: number) => client.post<{ id: number }>('/accounts', { name, balance }),
  createCategory: (name: string, parent_id: number | null = null, daily_pace_included=true, description?:string) => client.post<{ id: number }>('/categories', { name, parent_id, daily_pace_included, ...(description!==undefined?{description}:{}) }),
  updateCategory: (id: number, name: string, parent_id: number | null, version: number, daily_pace_included?:boolean, description?:string) => client.put<{ id: number }>('/categories/' + id, { name, parent_id, version, daily_pace_included, ...(description!==undefined?{description}:{}) }),
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
export interface PlanTransferInput {month:string;source_id:number;target_id:number;amount:number}
export interface PlanTransferPreview extends PlanTransferInput {token:string;source_name:string;target_name:string;source_before:number;source_after:number;target_before:number;target_after:number;total_before:number;total_after:number;related_limits?:{name:string;before:number;after:number}[]}
export interface BudgetYearPlan {start:string;months:{month:string;income:number;ordinary:number;payments:number;reserves:number;cost:number;remaining:number;spent:number;carryover:number;missing_plans:string[];sources:{id:number;name:string;source:string;amount:number}[]}[]}
export interface DefaultPlans {month:string;items:{category_id:number;name:string;parent_id:number|null;managed:boolean;amount:number|null;start_month:string|null;revision:string;history:{start_month:string;amount:number}[]}[]}
export interface PlanCopyInput {source:string;start:string;months:number;replace:boolean;category_ids:number[]}
export interface PlanCopyPreview {source:string;start:string;months:number;replace:boolean;copied:number;skipped:number;token:string;rows:{month:string;category_id:number;name:string;action:'ADD'|'REPLACE'|'KEEP'|'MANAGED'|'NO_SOURCE';amount:number;previous:number}[]}
