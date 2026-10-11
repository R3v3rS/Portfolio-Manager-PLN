import { createApiClient } from './apiConfig';

export type ReserveMovementKind = 'ADD' | 'RELEASE' | 'SPEND';
export interface ReservePlan {
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
  as_of: string; items: Reserve[];
  accounts: { id: number; name: string; balance: number; reserved: number; available: number }[];
  categories: { id: number; name: string; selection_label?: string }[]; warnings: string[];
  totals: { monthly_remaining?:number; saved: number; remaining: number; monthly_required: number; urgent_amount: number; active: number };
}
export interface ReserveMovementInput {
  kind: ReserveMovementKind; amount: number; date: string; notes: string;
  category_id?: number; account_id?:number;
  existing_entry_id?:number; entry_version?:number;
}
const client = createApiClient('/budget/reserves');
export const reservesApi = {
  get: () => client.get<ReservesWorkspace>(''),
  create: (plan: ReservePlan, request_id: string) => client.post<{id:number}>('',{...plan,request_id}),
  update: (id: number, plan: ReservePlan, version: number) => client.put<{id:number}>(`/${id}`,{...plan,version}),
  move: (id: number, input: ReserveMovementInput, version: number, request_id: string) =>
    client.post<{id:number;budget_entry_id:number|null}>(`/${id}/movements`,{...input,version,request_id}),
  archive: (id: number, archived: boolean, version: number) => client.put(`/${id}/archive`,{archived,version}),
};
