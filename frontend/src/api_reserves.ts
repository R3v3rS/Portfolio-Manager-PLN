import { createApiClient } from './apiConfig';

export type ReserveMovementKind = 'ADD' | 'RELEASE' | 'SPEND';
export interface ReservePlan {
  monthly_start_month?:string|null;
  open_ended?:boolean;
  monthly_amount?:number|null;
  category_id?:number|null;
  name: string; notes: string; account_id: number; target_amount: number;
  due_date: string; frequency: 'ONCE' | 'YEARLY';
}
export interface ReserveMovement {
  id: number; cycle: number; kind: ReserveMovementKind; amount: number;
  date: string; notes: string; expense_amount: number | null; budget_entry_id: number | null;
  account_id?:number; account_name?:string; budget_cost?:number;
}
export interface Reserve extends ReservePlan {
  journal?: ReserveJournalEvent[];
  month_statement?: ReserveMonthStatement;
  monthly_started?:boolean;
  month_planned?:number; month_allocated?:number;
  id: number; account_name: string; saved: number; start_date: string; cycle: number;
  version: number; status: 'ACTIVE' | 'COMPLETED' | 'ARCHIVED'; remaining: number;
  monthly_required: number; months_left: number; next_contribution_date: string | null;
  progress_percent: number; surplus: number; urgent: boolean; overdue: boolean;
  funded_this_month: boolean; movements: ReserveMovement[];
  locations?:{account_id:number;account_name:string;amount:number}[];
  transfers?:{id:number;amount:number;date:string;notes:string;source_account_name:string;target_account_name:string;move_money:boolean;reserve_action?:'MOVE'|'FUND'}[];
}
export interface ReservesWorkspace {
  month?:string;
  as_of: string; items: Reserve[];
  accounts: { id: number; name: string; balance: number; reserved: number; available: number }[];
  categories: { id: number; name: string; selection_label?: string }[]; warnings: string[];
  totals: { monthly_remaining?:number; saved: number; remaining: number; monthly_required: number; urgent_amount: number; active: number };
}
export interface ReserveMovementInput {
  kind: ReserveMovementKind; amount: number; date: string; notes: string;
  category_id?: number; account_id?:number;
  existing_entry_id?:number; entry_version?:number;
  surplus_mode?:'FREE'|'KEEP'|'RESERVE'; surplus_reserve_id?:number; surplus_reserve_version?:number;
  next_due_date?:string; expected_state?:string;
}
export interface ReserveAccountChange {account_id:number;account_name:string;balance_before:number;balance_after:number;reserved_before:number;reserved_after:number;available_before:number;available_after:number}
export interface ReserveSummary {
  kind:ReserveMovementKind;date:string;reserve_id:number;reserve_name:string;amount:number;reserve_before?:number;reserve_after?:number;
  covered:number;released:number;surplus:number;surplus_mode:'FREE'|'KEEP'|'RESERVE';surplus_reserve_name:string|null;
  existing_expense?:boolean;available_change?:number;accounts:ReserveAccountChange[];budget_entry_id:number|null;
}
export interface ReservePreview extends ReserveSummary {expected_state:string}
export interface ReserveJournalEvent {id:string;kind:ReserveMovementKind|'FUND'|'TRANSFER'|'REALLOCATE'|'REVERSAL';title:string;date:string;amount:number;reserve_change:number;bank_change:number;account_name:string;notes:string;transfer:{source:string;target:string;changes_cash?:boolean}|null;budget_entry_id:number|null;summary:ReserveSummary|null}
export interface ReserveMonthStatement {month:string;opening:number;added:number;used:number;released:number;payments:number;ending:number;planned?:number;funded?:number;remaining?:number;extra?:number}
export interface ReserveBatchRow {reserve_id:number;account_id:number;version:number;amount:number}
export interface ReserveFundingPlan {month:string;date:string;rows:{reserve_id:number;name:string;account_id:number;priority:number;remaining:number;proposed:number;version:number}[];remaining:number;proposed:number}
export interface ReserveBatchPreview {expected_state:string;total:number;accounts:ReserveAccountChange[];rows:{summary:ReserveSummary}[]}
export interface ReserveMoveResult {id:number;budget_entry_id:number|null;summary?:ReserveSummary}
const client = createApiClient('/budget/reserves');
export const reservesApi = {
  get: (month?:string) => client.get<ReservesWorkspace>(month?`?month=${encodeURIComponent(month)}`:''),
  create: (plan: ReservePlan, request_id: string) => client.post<{id:number}>('',{...plan,request_id}),
  update: (id: number, plan: ReservePlan, version: number) => client.put<{id:number}>(`/${id}`,{...plan,version}),
  move: (id: number, input: ReserveMovementInput, version: number, request_id: string) =>
    client.post<ReserveMoveResult>(`/${id}/movements`,{...input,version,request_id}),
  preview:(id:number,input:ReserveMovementInput,version:number)=>client.post<ReservePreview>(`/${id}/preview`,{...input,version}),
  fundingPlan:()=>client.get<ReserveFundingPlan>('/funding-plan'),
  fundingPreview:(input:{date:string;rows:ReserveBatchRow[]})=>client.post<ReserveBatchPreview>('/funding-preview',input),
  fundBatch:(input:{date:string;rows:ReserveBatchRow[];expected_state:string},request_id:string)=>client.post<ReserveBatchPreview>('/funding',{...input,request_id}),
  archive: (id: number, archived: boolean, version: number) => client.put(`/${id}/archive`,{archived,version}),
};
